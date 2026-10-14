"""Pydantic output contracts for every crew task.

Typed outputs are the backbone of the honesty guarantee: downstream agents
and guardrails consume these models, not free text, so a missing fact is a
missing field instead of an invented sentence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# Crew task outputs
# --------------------------------------------------------------------------- #
class WorkExperience(BaseModel):
    company: str = ""
    title: str = ""
    dates: str = ""
    achievements: list[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    full_name: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[WorkExperience] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)


class JobRequirements(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    seniority: str = ""
    nice_to_have: list[str] = Field(default_factory=list)


class GapVerdict(BaseModel):
    requirement: str
    verdict: str = Field(description="one of: covered, reframeable, out_of_scope")
    supporting_fact: str = ""


class GapReport(BaseModel):
    coverage_score: int = Field(ge=0, le=100, default=0)
    verdicts: list[GapVerdict] = Field(default_factory=list)


class RewrittenBullet(BaseModel):
    text: str
    cited_fact: str = Field(description="profile fact this bullet is based on")


class FeedbackDraft(BaseModel):
    rewritten_bullets: list[RewrittenBullet] = Field(default_factory=list)
    talking_points: list[str] = Field(default_factory=list)
    do_not_claim: list[str] = Field(default_factory=list)


class ScreeningAnswer(BaseModel):
    """One answer to an employer screening question.

    ``source`` must be ``"answer_bank"``: the only permitted origin for a
    screening fact. Unverified questions are routed to ``do_not_claim`` instead.
    """

    question: str
    answer: str = ""
    source: str = Field(default="answer_bank", description="must be 'answer_bank'")
    verified: bool = True


class ApplicationPackage(BaseModel):
    """The assembled application package produced by the packager agent."""

    package_id: str = ""
    role_title: str = ""
    company: str = ""
    screening_answers: list[ScreeningAnswer] = Field(default_factory=list)
    package_summary: str = ""
    do_not_claim: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Review / tracker
# --------------------------------------------------------------------------- #
class ReviewStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ReviewAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REVISE = "REVISE"


class ReviewDecision(BaseModel):
    package_id: str
    decision: ReviewAction
    reviewer_feedback: str = ""
    decided_at: datetime = Field(default_factory=_utcnow)


class TrackerEntry(BaseModel):
    """A row in the session tracker: what was prepared, and its status."""

    package_id: str
    role_title: str = ""
    company: str = ""
    status: ReviewStatus = ReviewStatus.DRAFT
    revision_count: int = 0
    prepared_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class TraceEvent(BaseModel):
    step: str
    actor: str = "pipeline"
    detail: str = ""
    status: str = "ok"  # ok | warning | error
    duration_ms: int | None = None


class ExecutionTrace(BaseModel):
    """A lightweight, human-readable record of one run for the UI panel."""

    events: list[TraceEvent] = Field(default_factory=list)

    def add(
        self,
        step: str,
        actor: str = "pipeline",
        detail: str = "",
        *,
        status: str = "ok",
        duration_ms: int | None = None,
    ) -> None:
        self.events.append(
            TraceEvent(
                step=step,
                actor=actor,
                detail=detail,
                status=status,
                duration_ms=duration_ms,
            )
        )
