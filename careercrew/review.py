"""Human approval of a prep bundle: approve, reject, or request changes.

What it does: moves a bundle through DRAFT, pending review, approved, or rejected.
Who calls it: the Approve, Reject, and Request changes buttons.
What it returns: the new review status, or ReviewError when the move is not allowed.
"""

from __future__ import annotations

from dataclasses import dataclass

from careercrew.config import get_settings
from careercrew.models import (
    ApplicationPackage,
    ReviewAction,
    ReviewDecision,
    ReviewStatus,
)
from careercrew.session_store import SessionStore


class ReviewError(RuntimeError):
    """Raised for invalid review transitions or exceeded revision limits."""


#: Valid transitions from each status.
_ALLOWED: dict[ReviewStatus, set[ReviewStatus]] = {
    ReviewStatus.DRAFT: {ReviewStatus.PENDING_REVIEW},
    ReviewStatus.PENDING_REVIEW: {
        ReviewStatus.APPROVED,
        ReviewStatus.REJECTED,
        ReviewStatus.DRAFT,  # a requested revision returns to a fresh draft
    },
    ReviewStatus.APPROVED: set(),
    ReviewStatus.REJECTED: set(),
}


def _check_transition(current: ReviewStatus, target: ReviewStatus) -> None:
    if target not in _ALLOWED[current]:
        raise ReviewError(f"invalid transition: {current.value} -> {target.value}")


@dataclass
class ReviewOutcome:
    """Result of applying a human review decision."""

    status: ReviewStatus
    message: str
    revision_count: int = 0
    needs_revision: bool = False


class PackageReviewService:
    """Coordinates package status changes and persistence."""

    def __init__(self, store: SessionStore, max_revisions: int | None = None) -> None:
        self._store = store
        self._max_revisions = (
            max_revisions if max_revisions is not None else get_settings().max_revisions
        )

    # -- lifecycle -------------------------------------------------------------
    def submit_for_review(
        self,
        inputs: dict,
        package: ApplicationPackage,
        trace=None,
        status: ReviewStatus = ReviewStatus.DRAFT,
        revision_count: int = 0,
    ) -> ReviewOutcome:
        """Persist a validated draft and move it into PENDING_REVIEW."""
        _check_transition(status, ReviewStatus.PENDING_REVIEW)
        self._store.save_package(inputs, package, trace, revision_count=revision_count)
        self._store.update_status(package.package_id, ReviewStatus.PENDING_REVIEW, revision_count)
        return ReviewOutcome(
            status=ReviewStatus.PENDING_REVIEW,
            message="Package submitted for human review.",
            revision_count=revision_count,
        )

    def apply_decision(
        self,
        package: ApplicationPackage,
        decision: ReviewDecision,
        current_status: ReviewStatus = ReviewStatus.PENDING_REVIEW,
        revision_count: int = 0,
    ) -> ReviewOutcome:
        """Apply an APPROVE / REJECT / REVISE decision to a package.

        Enforces valid transitions and the revision limit. Persists the decision
        and the resulting status.
        """
        if decision.package_id != package.package_id:
            raise ReviewError("decision does not match this package")

        if current_status is not ReviewStatus.PENDING_REVIEW:
            raise ReviewError(f"package is {current_status.value}, not awaiting review")

        if decision.decision is ReviewAction.APPROVE:
            _check_transition(current_status, ReviewStatus.APPROVED)
            self._persist(package, decision, ReviewStatus.APPROVED, revision_count)
            return ReviewOutcome(
                status=ReviewStatus.APPROVED,
                message="Package approved and finalized.",
                revision_count=revision_count,
            )

        if decision.decision is ReviewAction.REJECT:
            _check_transition(current_status, ReviewStatus.REJECTED)
            self._persist(package, decision, ReviewStatus.REJECTED, revision_count)
            return ReviewOutcome(
                status=ReviewStatus.REJECTED,
                message="Package rejected; it will not be finalized.",
                revision_count=revision_count,
            )

        # REVISE
        if not decision.reviewer_feedback.strip():
            raise ReviewError("a revision request requires reviewer feedback")
        next_count = revision_count + 1
        if next_count > self._max_revisions:
            raise ReviewError(
                f"revision limit reached ({self._max_revisions}); "
                "approve, reject, or start a new analysis."
            )
        _check_transition(current_status, ReviewStatus.DRAFT)
        self._store.record_decision(decision)
        self._store.update_status(package.package_id, ReviewStatus.DRAFT, next_count)
        return ReviewOutcome(
            status=ReviewStatus.DRAFT,
            message=(
                f"Revision {next_count} requested; merging candidate experience "
                "updates and re-analyzing."
            ),
            revision_count=next_count,
            needs_revision=True,
        )

    def _persist(
        self,
        package: ApplicationPackage,
        decision: ReviewDecision,
        status: ReviewStatus,
        revision_count: int,
    ) -> None:
        self._store.record_decision(decision)
        self._store.update_status(package.package_id, status, revision_count)

    # -- helpers ---------------------------------------------------------------
    def can_revise(self, revision_count: int) -> bool:
        """Whether another revision is still permitted."""
        return revision_count < self._max_revisions
