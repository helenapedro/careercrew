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
        return list(result)[-1]
    return result


def test_app_builds():
    import app

    demo = app.build_app()
    assert demo is not None


def test_custom_theme_and_css_exist():
    import app

    assert "cc-hero" in app.CUSTOM_CSS
    assert "cc-stage" in app.CUSTOM_CSS
    assert app.theme() is not None


def test_stage_tracker_reflects_progress():
    import app

    idle = app._stages_html(-1)
    assert "READY" in idle
    assert "Read resume" in idle
    running = app._stages_html(3, "Understanding the role…")
    assert "RUNNING" in running
    assert "DONE" in running  # stages 1 and 2 finished
    assert "Understanding the role…" in running
    done = app._stages_html(app._FINAL, "complete")
    assert "RUNNING" not in done


def test_candidate_facing_copy_hides_tech_jargon_in_hero():
    import app

    hero = app._hero()
    assert "Match your resume" in hero
    assert "CrewAI" not in hero
    assert "MCP" not in hero


def test_analyze_missing_resume_returns_error(monkeypatch, tmp_path):
    monkeypatch.setenv("CAREERCREW_UPLOAD_DIR", str(tmp_path))
    from careercrew import config

    config.reset_settings_cache()
    pytest.importorskip("gradio")
    import app

    outputs = _drain(app.analyze(None, "", None, "A real job description here.", ""))
    error_box = outputs[0]
    assert "resume" in str(error_box).lower()
    assert "cc-alert" in str(error_box).lower() or "something went wrong" in str(error_box).lower()


def test_analyze_missing_jd_returns_error(monkeypatch, tmp_path):
    monkeypatch.setenv("CAREERCREW_UPLOAD_DIR", str(tmp_path))
    from careercrew import config

    config.reset_settings_cache()
    pytest.importorskip("gradio")
    import app

    outputs = _drain(
        app.analyze(
            None,
            "ALEX RIVERA Backend Engineer. Skills: Python, FastAPI, AWS. Built APIs at scale.",
            None,
            "",
            "",
        )
    )
    assert "job description" in str(outputs[0]).lower()


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
            None,
            "We need a Python backend engineer with FastAPI and AWS.",
            "Are you authorized to work in the US?",
        )
    )
    package_json = outputs[8]
    assert "answer_bank" in package_json
    # The stage tracker ends fully complete and the prep plan is populated.
    assert "RUNNING" not in outputs[3]
    assert "Interview prep plan" in outputs[6] or "prep" in outputs[6].lower()
    assert "Verified answer" in outputs[7] or "answer_bank" in outputs[7]
    # The context bundle for the interview/coach tabs is serialized.
    assert "prep_plan" in str(outputs[15])


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
            None,
            "We need a Python backend engineer with FastAPI and AWS.",
            "",
        )
    )
    assert "answer_bank" in outputs[8] or "prep" in outputs[1].lower()
    assert "invalid resume path" not in str(outputs[0]).lower()
    assert "Resume rejected" not in outputs[1]


def test_analyze_jd_file_upload_end_to_end(monkeypatch, tmp_path):
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

    jd_source = Path("samples/sample_jd.txt")
    staged_jd = tmp_path / "gradio_tmp_jd.txt"
    shutil.copyfile(jd_source, staged_jd)

    outputs = _drain(
        app.analyze(
            None,
            "ALEX RIVERA Backend Engineer. Skills: Python, FastAPI, AWS. Built APIs at scale here.",
            str(staged_jd),
            "",
            "What is your notice period?",
        )
    )
    assert "Job description rejected" not in outputs[1]
    assert "Verified answer" in outputs[7] or "answer_bank" in outputs[7]
