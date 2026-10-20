"""Tests for the Pydantic models and their defaults."""

from __future__ import annotations

from careercrew.models import (
    AnswerEvaluation,
    ApplicationPackage,
    CandidateProfile,
    ChatMessage,
    FeedbackDraft,
    GapReport,
    InterviewPrepPlan,
    InterviewQuestion,
    InterviewTurnRole,
    MockInterviewSession,
    PrepFocus,
    ReviewAction,
    ReviewStatus,
    RewrittenBullet,
    ScreeningAnswer,
    ScreeningPrep,
    SeniorityAssessment,
    SeniorityBand,
    TrackerEntry,
    TranscriptTurn,
    seniority_band_from_label,
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


def test_screening_prep_is_application_package_alias():
    assert ScreeningPrep is ApplicationPackage


def test_seniority_band_labels_and_parser():
    from careercrew.models import infer_seniority_from_jd

    assert SeniorityBand.EARLY.label == "2-3 years"
    assert SeniorityBand.MID.label == "5-10 years"
    assert SeniorityBand.SENIOR.label == "10+ years"
    assert seniority_band_from_label("2-3 years") is SeniorityBand.EARLY
    assert seniority_band_from_label("5-10 years") is SeniorityBand.MID
    assert seniority_band_from_label("10+ years") is SeniorityBand.SENIOR
    assert seniority_band_from_label("senior") is SeniorityBand.SENIOR
    assert seniority_band_from_label("5+ years of Python experience") is SeniorityBand.MID
    assert seniority_band_from_label("10+ years building systems") is SeniorityBand.SENIOR
    assert infer_seniority_from_jd(
        "Senior Backend Engineer. Required: 5+ years building services."
    ) == "5-10 years"
    assert infer_seniority_from_jd("We need a great teammate.") == ""


def test_interview_prep_plan_defaults():
    plan = InterviewPrepPlan()
    assert plan.focus_areas == []
    assert isinstance(plan.seniority, SeniorityAssessment)
    assert plan.seniority.band is SeniorityBand.EARLY
    assert PrepFocus(area="Python").priority == "medium"
    focus = PrepFocus(area="Kubernetes", priority="high", suggested_share_pct=50)
    plan.focus_areas.append(focus)
    assert plan.focus_areas[0].suggested_share_pct == 50


def test_seniority_assessment_bounds():
    assessment = SeniorityAssessment(band=SeniorityBand.MID, confidence=60)
    assert assessment.band is SeniorityBand.MID
    assert assessment.confidence == 60


def test_mock_interview_session_roundtrip():
    session = MockInterviewSession(
        session_id="int-1",
        questions=[InterviewQuestion(index=0, text="Tell me about yourself.")],
        turns=[TranscriptTurn(role=InterviewTurnRole.INTERVIEWER, text="Tell me about yourself.")],
        evaluations=[AnswerEvaluation(question_index=0, score=70, improvements=["add a metric"])],
        overall_score=70,
        completed=True,
    )
    restored = MockInterviewSession.model_validate_json(session.model_dump_json())
    assert restored.session_id == "int-1"
    assert restored.turns[0].role is InterviewTurnRole.INTERVIEWER
    assert restored.evaluations[0].score == 70


def test_chat_message_defaults():
    message = ChatMessage()
    assert message.role == "user"
    assert message.content == ""
