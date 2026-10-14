"""Smoke tests for the Gradio app: it builds and its callbacks run offline."""

from __future__ import annotations

import pytest

pytest.importorskip("gradio")


def test_app_builds():
    import app

    demo = app.build_app()
    assert demo is not None


def test_analyze_missing_resume_returns_error(monkeypatch, tmp_path):
    monkeypatch.setenv("CAREERCREW_UPLOAD_DIR", str(tmp_path))
    from careercrew import config

    config.reset_settings_cache()
    pytest.importorskip("gradio")
    import app

    outputs = app.analyze(None, "", "A real job description here.", "", "")
    error_box = outputs[0]
    # Gradio update objects expose the value dict.
    assert "resume" in str(error_box).lower()


def test_analyze_pasted_resume_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setenv("CAREERCREW_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("CAREERCREW_DB_PATH", ":memory:")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from careercrew import config

    config.reset_settings_cache()
    pytest.importorskip("gradio")
    import app

    outputs = app.analyze(
        None,
        "ALEX RIVERA Backend Engineer. Skills: Python, FastAPI, AWS. Built APIs at scale here.",
        "We need a Python backend engineer with FastAPI and AWS.",
        "",
        "Are you authorized to work in the US?",
    )
    package_json = outputs[6]
    assert "answer_bank" in package_json
