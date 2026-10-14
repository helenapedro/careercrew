"""Tests for the Pydantic models and their defaults."""

from __future__ import annotations

from careercrew.models import (
    ApplicationPackage,
    CandidateProfile,
    FeedbackDraft,
    GapReport,
    ReviewAction,
    ReviewStatus,
    RewrittenBullet,
    ScreeningAnswer,
    TrackerEntry,
)


def test_candidate_profile_defaults_are_empty():
    profile = CandidateProfile()
    assert profile.skills == []
    assert profile.experience == []
    assert profile.full_name == ""


def test_gap_report_score_bounds():
    report = GapReport(coverage_score=0)
    assert report.coverage_score == 0
    report = GapReport(coverage_score=100)
    assert report.coverage_score == 100


def test_screening_answer_defaults_to_answer_bank():
    answer = ScreeningAnswer(question="q", answer="a")
    assert answer.source == "answer_bank"
    assert answer.verified is True


def test_application_package_defaults():
    package = ApplicationPackage(package_id="pkg-1")
    assert package.screening_answers == []
    assert package.do_not_claim == []


def test_feedback_draft_bullets_require_citation_field():
    bullet = RewrittenBullet(text="Built APIs", cited_fact="FastAPI APIs")
    draft = FeedbackDraft(rewritten_bullets=[bullet])
    assert draft.rewritten_bullets[0].cited_fact == "FastAPI APIs"


def test_review_enums_are_string_valued():
    assert ReviewStatus.PENDING_REVIEW.value == "PENDING_REVIEW"
    assert ReviewAction.REVISE.value == "REVISE"


def test_tracker_entry_roundtrip():
    entry = TrackerEntry(package_id="pkg-1", status=ReviewStatus.APPROVED)
    assert TrackerEntry.model_validate_json(entry.model_dump_json()).status is ReviewStatus.APPROVED
