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


def _out(updates, name):
    """Read one named output instead of relying on a positional index."""
    from careercrew.ui_state import OUTPUT_ORDER

    return updates[OUTPUT_ORDER.index(name)]


def test_app_builds():
    import app

    demo = app.build_app()
    assert demo is not None


def test_custom_theme_and_css_exist():
    import app

    assert "cc-hero" in app.CUSTOM_CSS
    assert "cc-stage" in app.CUSTOM_CSS
    assert "repeat(6, minmax(0, 1fr))" in app.CUSTOM_CSS
    assert "repeat(7, minmax(0, 1fr))" not in app.CUSTOM_CSS
    assert app.theme() is not None


def test_streaming_runs_hide_gradio_progress_chrome():
    """Gradio's default progress border stacks a blue rule on every output."""
    import app

    demo = app.build_app()
    streaming = {
        fn.show_progress for fn in demo.fns.values() if fn.fn in (app.analyze, app.request_revision)
    }
    assert streaming == {"hidden"}


def test_app_is_light_only_even_when_os_prefers_dark():
    """Gradio adds a ``dark`` class from the OS preference; the app must undo it."""
    import app

    script = app.LIGHT_MODE_JS
    assert 'classList.remove("dark")' in script
    assert "matchMedia" in script
    # The stylesheet must also neutralise Gradio's dark palette, so the first
    # paint (before the script runs) is not a navy flash on a light app.
    assert "body.dark" in app.CUSTOM_CSS
    assert "--body-background-fill: #f7f8fa !important" in app.CUSTOM_CSS
    assert "button.upload-container" in app.CUSTOM_CSS


def test_analyze_takes_resume_and_job_inputs_only():
    """Analyze match takes a resume and a job description, nothing else."""
    import inspect

    import app

    params = list(inspect.signature(app.analyze).parameters)
    assert params == ["resume_file", "resume_text", "jd_file", "jd_text"]
    assert "screening_text" not in app.CUSTOM_CSS


def test_analyze_disables_run_button_while_working(monkeypatch, tmp_path):
    """Pressing Analyze must lock the button until the run finishes."""
    monkeypatch.setenv("CAREERCREW_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("CAREERCREW_DB_PATH", ":memory:")
    from careercrew import config

    config.reset_settings_cache()
    pytest.importorskip("gradio")
    import app

    # Missing inputs: first yield locks the buttons, then the failure re-enables
    # them so the user is never stuck with a dead Analyze button.
    gen = app.analyze(None, "", None, "A real job description here.")
    first = next(gen)
    assert _out(first, "run_button")["interactive"] is False, "run button must disable immediately"
    assert _out(first, "clear_button")["interactive"] is False, "clear button must disable too"

    last = first
    for last in gen:  # noqa: B007 - keep the final yielded update
        pass
    assert _out(last, "run_button")["interactive"] is True, (
        "run button must come back after a failure"
    )
    assert _out(last, "clear_button")["interactive"] is True

    # The reset state used by Clear also leaves both buttons usable.
    reset = app._empty_outputs().as_tuple()
    assert _out(reset, "run_button")["interactive"] is True
    assert _out(reset, "clear_button")["interactive"] is True


def test_stage_tracker_reflects_progress():
    from careercrew.runner import FINAL_STAGE
    from careercrew.ui_html import _stages_html

    idle = _stages_html(-1)
    assert "READY" in idle
    assert "Read resume" in idle
    running = _stages_html(3, "Understanding the role…")
    assert "RUNNING" in running
    assert "DONE" in running  # stages 1 and 2 finished
    assert "Understanding the role…" in running
    done = _stages_html(FINAL_STAGE, "complete")
    assert "RUNNING" not in done


def test_candidate_facing_copy_hides_tech_jargon_in_hero():
    import app

    hero = app._hero()
    assert "Match your resume" in hero
    assert "Analyze match" in hero
    assert "CrewAI" not in hero
    assert "MCP" not in hero


def test_progress_copy_is_analyze_scoped():
    import app

    idle = app._stages_html(-1)
    assert "Analyze progress" in idle
    assert "only while" in idle.lower() or "prepared" in idle.lower()


def test_analyze_missing_resume_returns_error(monkeypatch, tmp_path):
    monkeypatch.setenv("CAREERCREW_UPLOAD_DIR", str(tmp_path))
    from careercrew import config

    config.reset_settings_cache()
    pytest.importorskip("gradio")
    import app

    outputs = _drain(app.analyze(None, "", None, "A real job description here."))
    error_box = _out(outputs, "error")
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
        )
    )
    assert "job description" in str(_out(outputs, "error")).lower()


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
        )
    )
    # stages · match · prep · … · ctx
    assert "RUNNING" not in _out(outputs, "stages")
    assert (
        "Interview prep plan" in _out(outputs, "prep_plan")
        or "prep" in _out(outputs, "prep_plan").lower()
    )
    assert "prep_plan" in str(_out(outputs, "context"))


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
        )
    )
    assert "prep" in _out(outputs, "prep_plan").lower()
    assert "invalid resume path" not in str(_out(outputs, "error")).lower()
    assert "Resume rejected" not in _out(outputs, "status")


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
        )
    )
    assert "Job description rejected" not in _out(outputs, "status")
    assert "prep" in _out(outputs, "prep_plan").lower()


def test_request_revision_reruns_analysis(monkeypatch, tmp_path):
    """Request changes merges new experience and rebuilds results (not status-only)."""
    monkeypatch.setenv("CAREERCREW_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("CAREERCREW_DB_PATH", ":memory:")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from careercrew import config

    config.reset_settings_cache()
    import importlib

    import app

    importlib.reload(app)

    analyzed = _drain(
        app.analyze(
            None,
            "ALEX RIVERA Backend Engineer. Skills: Python, FastAPI, AWS. Built APIs at scale here.",
            None,
            "We need a Python backend engineer with React and FastAPI. 5+ years experience.",
        )
    )
    package_state = _out(analyzed, "package")
    assert package_state is not None

    notes = "I have 5+ years of React experience building production SPAs."
    revised = _drain(app.request_revision(package_state, notes))
    status = _out(revised, "status")
    assert "revision" in str(status).lower()
    assert "ready" in str(status).lower()
    assert _out(revised, "package") is not None
    # Saved inputs now include the attested experience for further revisions.
    stored = app._STORE.get_package(_out(revised, "package")["package_id"])
    assert stored is not None
    assert "React" in (stored.get("inputs") or {}).get("resume_text", "")
    assert "CANDIDATE-ATTESTED" in (stored.get("inputs") or {}).get("resume_text", "")
    # Offline path surfaces the update in the match report (the rewrite cites it).
    assert "React" in _out(revised, "match_report")
    # Decision guide returns to "ready" after the automatic re-analyze.
    assert "Your decision" in _out(revised, "review_guide")
    fb = _out(revised, "notes")
    if isinstance(fb, dict):
        assert fb.get("value", "") == ""
    else:
        assert getattr(fb, "value", fb) in ("", None) or fb == ""


def test_merge_revision_into_resume_appends_attested_block():
    from careercrew.callbacks_analyze import _merge_revision_into_resume

    merged = _merge_revision_into_resume(
        None,
        "ALEX RIVERA. Skills: Python.",
        "I have 5+ years of React experience.",
    )
    assert "Python" in merged
    assert "CANDIDATE-ATTESTED UPDATE" in merged
    assert "5+ years of React" in merged


def test_context_round_trip_and_interview_start_work_offline(monkeypatch, tmp_path):
    """Regression: the interview tab crashed on missing model imports."""
    monkeypatch.setenv("CAREERCREW_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("CAREERCREW_DB_PATH", ":memory:")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from careercrew import config

    config.reset_settings_cache()
    import importlib

    import app

    importlib.reload(app)

    outputs = _drain(
        app.analyze(
            None,
            "ALEX RIVERA Backend Engineer. Skills: Python, FastAPI, AWS. Built APIs at scale.",
            None,
            "We need a Python backend engineer with FastAPI and AWS.",
        )
    )
    context = _out(outputs, "context")
    assert context is not None

    # Rebuilding typed models from the serialized context must not raise.
    from careercrew.callbacks_analyze import _context_models
    from careercrew.models import CandidateProfile, GapReport, InterviewPrepPlan, JobRequirements

    models = _context_models(__import__("json").loads(context))
    assert models["package_id"]
    assert isinstance(models["profile"], CandidateProfile)
    assert isinstance(models["requirements"], JobRequirements)
    assert isinstance(models["gaps"], GapReport)
    assert isinstance(models["prep_plan"], InterviewPrepPlan)

    # Starting the interview produces grounded questions without any API key.
    started = app.interview_start(context, 3)
    assert started[1], "an interviewer question must render"
    assert started[6], "the session must be serialized for the next turn"
