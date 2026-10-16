"""Tests for the analysis pipeline (deterministic MCP fallback, no LLM key)."""

from __future__ import annotations

import pytest

from careercrew.models import JobRequirements
from careercrew.pipeline import (
    AnalysisRequest,
    _parse_package,
    deterministic_package,
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
        screening_questions=[
            "Are you authorized to work in the US?",
            "What is your notice period?",
            "Do you hold a PhD in astrophysics?",
        ],
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
    assert len(result.package.screening_answers) == 2
    assert result.package.do_not_claim == ["Do you hold a PhD in astrophysics?"]


def test_run_analysis_all_answers_from_answer_bank(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from careercrew import config

    config.reset_settings_cache()
    result = run_analysis(_request())
    assert all(a.source == "answer_bank" for a in result.package.screening_answers)


def test_run_analysis_produces_prep_plan(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from careercrew import config

    config.reset_settings_cache()
    result = run_analysis(_request())
    # Even without an LLM, the prep plan is derived from the gaps.
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


def test_deterministic_package_marks_unknown_as_do_not_claim():
    from careercrew.mcp_client import MCPToolClient
    from careercrew.models import ExecutionTrace

    trace = ExecutionTrace()
    request = _request(
        screening_questions=["Are you willing to relocate?", "What is your spirit animal?"]
    )
    package = deterministic_package(request, trace, MCPToolClient())
    assert len(package.screening_answers) == 1
    assert package.do_not_claim == ["What is your spirit animal?"]


def test_parse_package_repairs_and_skips_empty_answers():
    data = {
        "role_title": "Backend Engineer",
        "company": "Acme",
        "screening_answers": [
            {"question": "q1", "answer": "a1"},
            {"question": "q2", "answer": ""},  # skipped
            "junk",  # skipped
        ],
        "do_not_claim": "q3",
    }
    package = _parse_package(data, "pkg-1")
    assert package.role_title == "Backend Engineer"
    assert len(package.screening_answers) == 1
    assert package.screening_answers[0].source == "answer_bank"
    assert package.do_not_claim == ["q3"]


def test_parse_package_returns_none_on_junk():
    assert _parse_package("not a dict", "pkg-1") is None


def test_make_package_id_is_unique():
    assert make_package_id() != make_package_id()


def test_pipeline_fills_default_models(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from careercrew import config

    config.reset_settings_cache()
    result = run_analysis(_request())
    assert isinstance(result.requirements, JobRequirements)
    assert result.trace.events  # a trace was recorded
