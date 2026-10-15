"""Smoke tests for the Gradio app: it builds and its callbacks run offline."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytest.importorskip("gradio")


def _drain(result):
    """Normalize analyze() which may return a tuple or yield updates."""
    import inspect

    if isinstance(result, tuple):
        return result
    if inspect.isgenerator(result):
        outputs = None
        for outputs in result:
            pass
        return outputs
    return result


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

    outputs = _drain(app.analyze(None, "", "A real job description here.", "", ""))
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
    import importlib
    import app

    importlib.reload(app)

    outputs = _drain(
        app.analyze(
            None,
            "ALEX RIVERA Backend Engineer. Skills: Python, FastAPI, AWS. Built APIs at scale here.",
            "We need a Python backend engineer with FastAPI and AWS.",
            "",
            "Are you authorized to work in the US?",
        )
    )
    package_json = outputs[6]
    assert "answer_bank" in package_json


def test_analyze_file_upload_end_to_end(monkeypatch, tmp_path):
    """Regression: file uploads used to fail the relative-vs-absolute path check."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setenv("CAREERCREW_UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("CAREERCREW_DB_PATH", ":memory:")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from careercrew import config

    config.reset_settings_cache()
    import importlib
    import app

    importlib.reload(app)

    source = Path("samples/sample_resume.txt")
    staged = tmp_path / "gradio_tmp_resume.txt"
    shutil.copyfile(source, staged)

    outputs = _drain(
        app.analyze(
            str(staged),
            "",
            "We need a Python backend engineer with FastAPI and AWS.",
            "",
            "What is your notice period?",
        )
    )
    assert "answer_bank" in outputs[6] or "package" in outputs[1].lower()
    assert "invalid resume path" not in str(outputs[0]).lower()
    assert "Resume rejected" not in outputs[1]
