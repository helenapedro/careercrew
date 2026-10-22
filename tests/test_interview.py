"""Tests for the virtual mock interviewer (deterministic, no LLM / audio key)."""

from __future__ import annotations

from careercrew import interview
from careercrew.models import (
    CandidateProfile,
    GapReport,
    GapVerdict,
    InterviewTurnRole,
    JobRequirements,
    MockInterviewSession,
)


def _inputs():
    profile = CandidateProfile(full_name="Alex", skills=["Python", "FastAPI"])
    requirements = JobRequirements(required_skills=["Python", "AWS"], seniority="Mid")
    gaps = GapReport(
        coverage_score=50,
        verdicts=[
            GapVerdict(requirement="Python", verdict="covered", supporting_fact="Python"),
            GapVerdict(requirement="AWS", verdict="out_of_scope", supporting_fact=""),
        ],
    )
    return profile, requirements, gaps


def test_generate_questions_without_llm():
    profile, requirements, gaps = _inputs()
    questions = interview.generate_questions(profile, requirements, gaps, None, 5)
    assert 1 <= len(questions) <= 5
    assert all(q.text for q in questions)
    # The out-of-scope gap should be probed early.
    assert any("AWS" in q.text for q in questions)


def test_generate_questions_uses_llm():
    profile, requirements, gaps = _inputs()

    def fake_llm(prompt: str) -> str:
        return '{"questions": [{"text": "Q one?", "intent": "I", "target_competency": "C", "source": "S"}]}'

    questions = interview.generate_questions(profile, requirements, gaps, None, 3, llm=fake_llm)
    assert len(questions) == 1
    assert questions[0].text == "Q one?"


def test_evaluate_answer_fallback_rewards_specifics():
    profile, requirements, gaps = _inputs()
    question = interview.generate_questions(profile, requirements, gaps, None, 1)[0]
    weak = interview.evaluate_answer(question, "I did stuff.", {})
    strong = interview.evaluate_answer(
        question,
        "I built a REST API in FastAPI that served 2M requests per day and reduced "
        "latency by 40%, leading the migration myself.",
        {},
    )
    assert strong.score > weak.score
    assert weak.improvements
    assert strong.what_interviewer_wanted


def test_evaluation_is_kept_per_answer():
    session = MockInterviewSession(session_id="s1")
    profile, requirements, gaps = _inputs()
    question = interview.generate_questions(profile, requirements, gaps, None, 1)[0]
    session.evaluations.append(interview.evaluate_answer(question, "A short answer.", {}))
    assert 0 <= session.evaluations[0].score <= 100
    assert session.evaluations[0].improvements


def test_session_has_no_overall_score_fields():
    session = MockInterviewSession(session_id="s1")
    assert not hasattr(session, "overall_score")
    assert not hasattr(session, "overall_summary")
    assert not hasattr(interview, "overall_evaluation")


def test_append_turn_validates_and_records():
    session = MockInterviewSession(session_id="s1")
    turn = interview.append_turn(session, InterviewTurnRole.INTERVIEWER, "Hello?", question_index=0)
    assert turn.text == "Hello?"
    assert session.turns[-1].role is InterviewTurnRole.INTERVIEWER


def test_make_session_id_is_unique():
    assert interview.make_session_id() != interview.make_session_id()
