"""Tests for the analysis pipeline (gap-based fallback, no LLM key)."""

from __future__ import annotations

import pytest

from careercrew.models import JobRequirements
from careercrew.pipeline import (
    AnalysisRequest,
    make_package_id,
    run_analysis,
)


def _request(**overrides) -> AnalysisRequest:
    base = dict(
        package_id="pkg-test",
        resume_text=(
            "ALEX RIVERA Backend Engineer. Skills: Python, FastAPI, AWS. "
            "Built REST APIs serving 2M requests per day."
        ),
        jd_text="We need a Python backend engineer with FastAPI and AWS experience.",
        seniority="5-10 years",
    )
    base.update(overrides)
    return AnalysisRequest(**base)


def test_run_analysis_falls_back_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from careercrew import config

    config.reset_settings_cache()
    result = run_analysis(_request())
    assert result.used_fallback is True
    assert result.package.package_id == "pkg-test"
    assert result.prep_plan is not None


def test_run_analysis_produces_prep_plan(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from careercrew import config

    config.reset_settings_cache()
    result = run_analysis(_request())
    # Even without an LLM, the prep plan is derived from the gaps.
    assert result.prep_plan.seniority.band.value == "mid"
    assert result.prep_plan.seniority.target_years == "5-10 years"


def test_apply_revision_experience_covers_matching_requirement():
    from careercrew.models import GapReport, GapVerdict, JobRequirements
    from careercrew.pipeline import AnalysisRequest, _apply_revision_experience

    request = AnalysisRequest(
        package_id="pkg-rev",
        resume_text="Python engineer",
        jd_text="Need React and Python. 5 years React required.",
        revision_notes="I have 5+ years of React experience building SPAs.",
    )
    profile, gaps, reqs = _apply_revision_experience(
        None,
        GapReport(
            coverage_score=20,
            verdicts=[
                GapVerdict(requirement="React", verdict="out_of_scope", supporting_fact=""),
                GapVerdict(requirement="Python", verdict="covered", supporting_fact="resume"),
            ],
        ),
        JobRequirements(required_skills=["React", "Python"]),
        request,
    )
    assert any("Candidate-attested" in r.company for r in profile.experience)
    react = next(v for v in gaps.verdicts if v.requirement == "React")
    assert react.verdict == "covered"
    assert "React" in react.supporting_fact


def test_run_analysis_infers_seniority_from_jd(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from careercrew import config

    config.reset_settings_cache()
    result = run_analysis(
        _request(
            seniority="",
            jd_text=(
                "Senior Backend Engineer. Required: 5+ years building backend "
                "services in Python."
            ),
        )
    )
    assert result.prep_plan.seniority.band.value == "mid"
    assert result.prep_plan.seniority.target_years == "5-10 years"


def test_run_analysis_rejects_bad_inputs():
    with pytest.raises(ValueError):
        run_analysis(AnalysisRequest(package_id="pkg-x", jd_text=""))


def test_run_analysis_rejects_jd_url(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from careercrew import config, document_tools

    config.reset_settings_cache()
    with pytest.raises(document_tools.JobDescriptionError):
        run_analysis(_request(jd_text="https://example.com/job"))


def test_make_package_id_is_unique():
    assert make_package_id() != make_package_id()


def test_pipeline_fills_default_models(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from careercrew import config

    config.reset_settings_cache()
    result = run_analysis(_request())
    assert isinstance(result.requirements, JobRequirements)
    assert result.trace.events  # a trace was recorded
