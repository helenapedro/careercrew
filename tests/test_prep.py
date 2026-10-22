"""Tests for the Interview Preparation Advisor (deterministic, no LLM key)."""

from __future__ import annotations

from careercrew.models import (
    CandidateProfile,
    GapReport,
    GapVerdict,
    JobRequirements,
    SeniorityBand,
    seniority_band_from_label,
)
from careercrew.prep import build_fallback_plan, build_prep_plan, merge_plan


def _gaps() -> GapReport:
    return GapReport(
        coverage_score=55,
        verdicts=[
            GapVerdict(requirement="Python", verdict="covered", supporting_fact="Python"),
            GapVerdict(requirement="Kubernetes", verdict="reframeable", supporting_fact="Docker"),
            GapVerdict(requirement="Team leadership", verdict="out_of_scope", supporting_fact=""),
        ],
    )


def test_band_from_label():
    assert seniority_band_from_label("2-3 years") is SeniorityBand.EARLY
    assert seniority_band_from_label("5-10 years") is SeniorityBand.MID
    assert seniority_band_from_label("10+ years") is SeniorityBand.SENIOR
    assert seniority_band_from_label("senior") is SeniorityBand.SENIOR


def test_fallback_plan_prioritises_out_of_scope():
    plan = build_fallback_plan(
        CandidateProfile(full_name="Alex", skills=["Python"]),
        JobRequirements(required_skills=["Python"], seniority="Senior"),
        _gaps(),
        "10+ years",
    )
    assert plan.seniority.band is SeniorityBand.SENIOR
    assert plan.focus_areas[0].area == "Team leadership"
    assert plan.focus_areas[0].priority == "high"
    assert "Team leadership" in plan.risk_areas
    assert "Python" in plan.strengths


def test_fallback_plan_shares_total_about_100():
    plan = build_fallback_plan(CandidateProfile(), JobRequirements(), _gaps(), "2-3 years")
    total = sum(focus.suggested_share_pct for focus in plan.focus_areas)
    assert 80 <= total <= 120


def test_fallback_plan_evidence_is_grounded():
    plan = build_fallback_plan(CandidateProfile(), JobRequirements(), _gaps(), "2-3 years")
    requirements = {v.requirement for v in _gaps().verdicts}
    for focus in plan.focus_areas:
        assert focus.evidence in requirements


def test_build_prep_plan_without_llm_returns_fallback():
    plan = build_prep_plan(CandidateProfile(), JobRequirements(), _gaps(), "5-10 years")
    assert plan.focus_areas


def test_build_prep_plan_uses_llm_when_available():
    def fake_llm(prompt: str) -> str:
        assert "Interview Preparation Advisor" in prompt
        return (
            '{"seniority": {"band": "senior", "target_years": "10+ years", '
            '"detected_years": "8 roles", "confidence": 80, "rationale": "senior"}, '
            '"focus_areas": [{"area": "Leadership", "priority": "high", '
            '"suggested_share_pct": 100, "why": "gap", "evidence": "Team leadership"}], '
            '"question_themes": ["Design"], "strengths": ["Python"], "risk_areas": ["Leadership"]}'
        )

    plan = build_prep_plan(
        CandidateProfile(), JobRequirements(), _gaps(), "10+ years", llm=fake_llm
    )
    assert plan.seniority.band is SeniorityBand.SENIOR
    assert plan.question_themes == ["Design"]


def test_merge_plan_falls_back_on_junk():
    fallback = build_fallback_plan(CandidateProfile(), JobRequirements(), _gaps(), "2-3 years")
    assert merge_plan("not json", fallback) is fallback
