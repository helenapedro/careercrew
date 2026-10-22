"""Tests for the HITL review state machine."""

from __future__ import annotations

import pytest

from careercrew.models import (
    ApplicationPackage,
    ReviewAction,
    ReviewDecision,
    ReviewStatus,
)
from careercrew.review import PackageReviewService, ReviewError
from careercrew.session_store import SessionStore


def _package(package_id: str = "pkg-1") -> ApplicationPackage:
    return ApplicationPackage(package_id=package_id, package_summary="summary")


def _service(max_revisions: int = 2) -> tuple[SessionStore, PackageReviewService]:
    store = SessionStore(":memory:")
    return store, PackageReviewService(store, max_revisions=max_revisions)


def test_submit_moves_to_pending_review():
    store, service = _service()
    outcome = service.submit_for_review({"jd_source": "x"}, _package())
    assert outcome.status is ReviewStatus.PENDING_REVIEW
    assert store.get_package("pkg-1")["status"] == "PENDING_REVIEW"


def test_approve_transitions_to_approved():
    store, service = _service()
    service.submit_for_review({"jd_source": "x"}, _package())
    outcome = service.apply_decision(
        _package(),
        ReviewDecision(package_id="pkg-1", decision=ReviewAction.APPROVE),
    )
    assert outcome.status is ReviewStatus.APPROVED
    assert store.get_package("pkg-1")["status"] == "APPROVED"


def test_reject_transitions_to_rejected():
    store, service = _service()
    service.submit_for_review({"jd_source": "x"}, _package())
    outcome = service.apply_decision(
        _package(),
        ReviewDecision(package_id="pkg-1", decision=ReviewAction.REJECT),
    )
    assert outcome.status is ReviewStatus.REJECTED


def test_revise_requires_feedback():
    store, service = _service()
    service.submit_for_review({"jd_source": "x"}, _package())
    with pytest.raises(ReviewError):
        service.apply_decision(
            _package(),
            ReviewDecision(package_id="pkg-1", decision=ReviewAction.REVISE),
        )


def test_revise_increments_and_respects_limit():
    store, service = _service(max_revisions=1)
    service.submit_for_review({"jd_source": "x"}, _package())
    outcome = service.apply_decision(
        _package(),
        ReviewDecision(package_id="pkg-1", decision=ReviewAction.REVISE, reviewer_feedback="tighten"),
    )
    assert outcome.needs_revision is True
    assert outcome.revision_count == 1

    # Re-submit the revised draft, then try to revise again beyond the limit.
    service.submit_for_review({"jd_source": "x"}, _package(), revision_count=1)
    with pytest.raises(ReviewError):
        service.apply_decision(
            _package(),
            ReviewDecision(package_id="pkg-1", decision=ReviewAction.REVISE, reviewer_feedback="again"),
            revision_count=1,
        )


def test_decide_on_wrong_status_is_rejected():
    store, service = _service()
    with pytest.raises(ReviewError):
        service.apply_decision(
            _package(),
            ReviewDecision(package_id="pkg-1", decision=ReviewAction.APPROVE),
            current_status=ReviewStatus.APPROVED,
        )


def test_decision_package_mismatch_is_rejected():
    store, service = _service()
    with pytest.raises(ReviewError):
        service.apply_decision(
            _package("pkg-a"),
            ReviewDecision(package_id="pkg-b", decision=ReviewAction.APPROVE),
        )
