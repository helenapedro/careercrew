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


class ScreeningPrep(BaseModel):
    """Copy-ready screening answers prepared for the candidate.

    Nothing is submitted anywhere. This is a candidate-facing bundle of answers
    drawn only from the verified answer bank, plus the questions that need the
    candidate's own input.
    """

    package_id: str = ""
    role_title: str = ""
    company: str = ""
    screening_answers: list[ScreeningAnswer] = Field(default_factory=list)
    package_summary: str = ""
    do_not_claim: list[str] = Field(default_factory=list)


# Backwards-compatible alias (older code/tests referenced the old name).
ApplicationPackage = ScreeningPrep


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


# --------------------------------------------------------------------------- #
# Interview preparation (seniority + gap driven)
# --------------------------------------------------------------------------- #
class SeniorityBand(str, Enum):
    """Target experience band the candidate is preparing for."""

    EARLY = "early"  # ~2-3 years
    MID = "mid"  # ~5-10 years
    SENIOR = "senior"  # ~10+ years

    @property
    def label(self) -> str:
        return {
            SeniorityBand.EARLY: "2-3 years",
            SeniorityBand.MID: "5-10 years",
            SeniorityBand.SENIOR: "10+ years",
        }[self]


def seniority_band_from_label(label: str) -> SeniorityBand:
    """Map a UI label (or a band value) onto a :class:`SeniorityBand`."""
    key = (label or "").strip().lower()
    # Match the explicit UI labels first (they overlap: "5-10" contains "10").
    if "10+" in key or "10 +" in key:
        return SeniorityBand.SENIOR
    if "5-10" in key or "5 - 10" in key:
        return SeniorityBand.MID
    if "2-3" in key or "2 - 3" in key:
        return SeniorityBand.EARLY
    if "senior" in key:
        return SeniorityBand.SENIOR
    if "mid" in key:
        return SeniorityBand.MID
    return SeniorityBand.EARLY


class SeniorityAssessment(BaseModel):
    """How close the candidate's experience is to the target band."""

    band: SeniorityBand = SeniorityBand.EARLY
    target_years: str = ""
    detected_years: str = ""
    confidence: int = Field(ge=0, le=100, default=0)
    rationale: str = ""


class PrepFocus(BaseModel):
    """One area the candidate should spend preparation time on.

    ``evidence`` must reference a real gap verdict (requirement text), so the
    advice stays grounded in the actual resume-vs-JD comparison.
    """

    area: str
    priority: str = Field(default="medium", description="one of: high, medium, low")
    suggested_share_pct: int = Field(ge=0, le=100, default=0)
    why: str = ""
    evidence: str = ""


class InterviewPrepPlan(BaseModel):
    """The output of the Interview Preparation Advisor."""

    seniority: SeniorityAssessment = Field(default_factory=SeniorityAssessment)
    focus_areas: list[PrepFocus] = Field(default_factory=list)
    question_themes: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    risk_areas: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Virtual mock interview
# --------------------------------------------------------------------------- #
class InterviewQuestion(BaseModel):
    """A single interviewer question, grounded in the application context."""

    index: int = 0
    text: str = ""
    intent: str = ""
    target_competency: str = ""
    source: str = Field(default="", description="the JD/resume area this comes from")
    audio_ref: str = ""


class InterviewTurnRole(str, Enum):
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


class TranscriptTurn(BaseModel):
    """One line of the live synchronized transcript."""

    role: InterviewTurnRole = InterviewTurnRole.INTERVIEWER
    text: str = ""
    question_index: int = 0
    created_at: datetime = Field(default_factory=_utcnow)
    audio_ref: str = ""


class AnswerEvaluation(BaseModel):
    """Real-time per-question critique shown right after an answer."""

    question_index: int = 0
    question: str = ""
    answer: str = ""
    score: int = Field(ge=0, le=100, default=0)
    what_interviewer_wanted: str = ""
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    model_answer_outline: list[str] = Field(default_factory=list)


class MockInterviewSession(BaseModel):
    """Everything produced by one mock interview."""

    session_id: str = ""
    role_title: str = ""
    questions: list[InterviewQuestion] = Field(default_factory=list)
    turns: list[TranscriptTurn] = Field(default_factory=list)
    evaluations: list[AnswerEvaluation] = Field(default_factory=list)
    overall_score: int = Field(ge=0, le=100, default=0)
    overall_summary: str = ""
    completed: bool = False


class ChatMessage(BaseModel):
    """A persisted chat turn for either coaching channel."""

    role: str = "user"  # user | assistant
    content: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
