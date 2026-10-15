"""CareerCrew - Gradio web interface.

A single page that drives the whole workflow:

1. Provide a resume (upload a PDF/DOCX/TXT file **or** paste the text) and a job
   description (paste text or an https URL).
2. Optionally paste employer screening questions.
3. Press **Run analysis** to run the five-agent crew through real MCP tools.
4. See the agent trace, the coverage/gap report, the feedback draft, and the
   assembled application package.
5. **Approve**, **Reject**, or **Request revision** (with feedback).
6. See the session tracker of packages prepared so far.

The UI never fabricates an analysis: with no LLM key it falls back to real MCP
screening-answer retrieval and says so. A JD URL that cannot be accessed is
shown as a clean error instead of crashing.
"""

from __future__ import annotations

import logging
import os
import shutil

import gradio as gr

from careercrew import guardrails
from careercrew.config import get_settings
from careercrew.models import (
    ApplicationPackage,
    ReviewAction,
    ReviewDecision,
    ReviewStatus,
)
from careercrew.pipeline import AnalysisRequest, make_package_id, run_analysis
from careercrew.review import PackageReviewService, ReviewError
from careercrew.session_store import SessionStore

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger("careercrew.app")

_SETTINGS = get_settings()
_STORE = SessionStore(_SETTINGS.db_path)
_REVIEW = PackageReviewService(_STORE)

os.makedirs(_SETTINGS.upload_dir, exist_ok=True)


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #
def _mode_banner() -> str:
    if _SETTINGS.has_llm:
        return (
            "<div style='padding:8px 12px;border-radius:8px;background:#e6f4ea;"
            "border:1px solid #34a853;color:#0b3d13;'>"
            "<b>AGENTS ENABLED</b> — the five-agent crew runs through real MCP "
            f"tools ({_SETTINGS.openai_model}).</div>"
        )
    return (
        "<div style='padding:8px 12px;border-radius:8px;background:#fef7e0;"
        "border:1px solid #f9ab00;color:#5f4300;'>"
        "<b>FALLBACK MODE</b> — no OPENAI_API_KEY is set. Screening answers are "
        "still retrieved through real MCP calls and shown honestly; add a key for "
        "the full agent crew.</div>"
    )


def _trace_markdown(result) -> str:
    if not result:
        return (
            "**Workflow stages**\n\n"
            "1. Input guardrails validate the resume and job description.\n"
            "2. Profile Extractor reads the resume via MCP `read_resume`.\n"
            "3. JD Analyzer reads the job description via MCP `fetch_job_description`.\n"
            "4. Gap Analyst scores coverage and labels each requirement.\n"
            "5. Feedback Writer drafts cited bullets and talking points.\n"
            "6. Application Packager answers screening questions via MCP `query_answer_bank`.\n"
            "7. Output guardrails validate the package, then it awaits your review."
        )
    lines = []
    for event in result.trace.events:
        marker = {"ok": "PASS", "warning": "WARN", "error": "FAIL"}[event.status]
        duration = f" ({event.duration_ms} ms)" if event.duration_ms is not None else ""
        lines.append(f"- `{marker}` **{event.step}** — {event.detail}{duration}")
    if result.warnings:
        lines.append("\n**Warnings**")
        lines.extend(f"- {warning}" for warning in result.warnings)
    return "\n".join(lines)


def _gaps_markdown(result) -> str:
    if not result:
        return "The coverage report will appear here after analysis."
    gaps = result.gaps
    lines = [f"**Coverage score:** {gaps.coverage_score}/100", ""]
    if gaps.verdicts:
        lines.append("| Requirement | Verdict | Supporting fact |")
        lines.append("|---|---|---|")
        for verdict in gaps.verdicts:
            lines.append(
                f"| {verdict.requirement} | {verdict.verdict} | {verdict.supporting_fact} |"
            )
    else:
        lines.append("_No requirement verdicts were produced._")
    return "\n".join(lines)


def _feedback_markdown(result) -> str:
    if not result:
        return "The feedback draft will appear here after analysis."
    feedback = result.feedback
    lines = ["**Rewritten bullets**", ""]
    for bullet in feedback.rewritten_bullets:
        lines.append(f"- {bullet.text}  \n  _cited:_ {bullet.cited_fact}")
    lines.append("\n**Interview talking points**")
    lines.extend(f"- {point}" for point in feedback.talking_points or ["_(none)_"])
    if feedback.do_not_claim:
        lines.append("\n**Do not claim (out of scope)**")
        lines.extend(f"- {item}" for item in feedback.do_not_claim)
    return "\n".join(lines)


def _tracker_rows() -> list[list]:
    rows = []
    for entry in _STORE.list_packages(limit=50):
        rows.append(
            [
                entry.package_id,
                entry.role_title,
                entry.company,
                entry.status.value,
                entry.revision_count,
                entry.updated_at.astimezone().strftime("%Y-%m-%d %H:%M"),
            ]
        )
    return rows


def _empty_outputs():
    return (
        gr.update(value="", visible=False),  # error box
        "Idle. Provide a resume and a job description, then press **Run analysis**.",
        _mode_banner(),
        _trace_markdown(None),
        _gaps_markdown(None),
        _feedback_markdown(None),
        "",  # package json
        gr.update(interactive=False),  # approve
        gr.update(interactive=False),  # reject
        gr.update(interactive=False),  # revise
        None,  # state
        "",  # review feedback
    )


# --------------------------------------------------------------------------- #
# Callbacks
# --------------------------------------------------------------------------- #
def _resolve_resume(resume_file, resume_text: str) -> tuple[str | None, str | None]:
    """Copy an uploaded file into the uploads folder, or use pasted text."""
    if resume_file:
        # Gradio 6 File may return a path string, a tempfile object, or a 1-item list.
        if isinstance(resume_file, (list, tuple)):
            resume_file = resume_file[0] if resume_file else None
        if resume_file is None:
            pass
        else:
            check_name = resume_file if isinstance(resume_file, str) else getattr(
                resume_file, "name", str(resume_file)
            )
            guardrails.check_upload(check_name)
            os.makedirs(_SETTINGS.upload_dir, exist_ok=True)
            base = os.path.abspath(_SETTINGS.upload_dir)
            destination = os.path.abspath(
                os.path.join(base, os.path.basename(check_name))
            )
            if not destination.startswith(base + os.sep):
                raise ValueError("invalid resume path")
            shutil.copyfile(check_name, destination)
            return os.path.basename(destination), None
    if (resume_text or "").strip():
        return None, guardrails.redact_pii(resume_text)
    return None, None


def analyze(resume_file, resume_text, jd_text, jd_url, screening_text):
    (
        error_box,
        status,
        banner,
        trace_md,
        gaps_md,
        feedback_md,
        package_json,
        approve,
        reject,
        revise,
        state,
        feedback,
    ) = _empty_outputs()

    jd_source = (jd_url or "").strip() or (jd_text or "").strip()

    try:
        resume_path, pasted = _resolve_resume(resume_file, resume_text)
    except Exception as exc:  # noqa: BLE001 - surface a clean error
        yield (
            gr.update(value=f"Resume error: {exc}", visible=True),
            "Resume rejected.",
            _mode_banner(),
            trace_md,
            gaps_md,
            feedback_md,
            package_json,
            approve,
            reject,
            revise,
            None,
            feedback,
        )
        return

    if resume_path is None and pasted is None:
        yield (
            gr.update(
                value="Provide a resume: upload a PDF/DOCX/TXT file or paste the text.",
                visible=True,
            ),
            "Missing resume.",
            _mode_banner(),
            trace_md,
            gaps_md,
            feedback_md,
            package_json,
            approve,
            reject,
            revise,
            None,
            feedback,
        )
        return

    questions = [line.strip() for line in (screening_text or "").splitlines() if line.strip()]
    request = AnalysisRequest(
        package_id=make_package_id(),
        resume_path=resume_path,
        resume_text=pasted,
        jd_source=guardrails.redact_pii(jd_source),
        screening_questions=questions,
    )

    # Re-validate the JD text path here (URL access is checked inside the pipeline).
    if not jd_source.strip():
        yield (
            gr.update(value="Paste a job description or an https URL.", visible=True),
            "Missing job description.",
            _mode_banner(),
            trace_md,
            gaps_md,
            feedback_md,
            package_json,
            approve,
            reject,
            revise,
            None,
            feedback,
        )
        return

    # Yield an immediate status so the UI does not look frozen during the
    # 1–3 minute crew run (Gradio treats this function as a generator).
    yield (
        gr.update(value="", visible=False),
        "Running analysis — the five-agent crew usually takes 1–3 minutes…",
        _mode_banner(),
        "Working…\n\n1. Profile Extractor\n2. JD Analyzer\n3. Gap Analyst\n"
        "4. Feedback Writer\n5. Application Packager",
        gaps_md,
        feedback_md,
        package_json,
        approve,
        reject,
        revise,
        None,
        feedback,
    )

    try:
        result = run_analysis(request)
    except Exception as exc:  # noqa: BLE001 - surface a clean error, never crash
        logger.exception("analysis run failed")
        yield (
            gr.update(value=f"Analysis failed: {exc}", visible=True),
            "Analysis failed.",
            _mode_banner(),
            trace_md,
            gaps_md,
            feedback_md,
            package_json,
            approve,
            reject,
            revise,
            None,
            feedback,
        )
        return

    _REVIEW.submit_for_review(
        {
            "resume_path": request.resume_path,
            "jd_source": request.jd_source,
            "screening_questions": request.screening_questions,
        },
        result.package,
        result.trace,
    )

    status = (
        f"Draft ready for review — package `{result.package.package_id}`, "
        f"{len(result.package.screening_answers)} screening answer(s), "
        f"{len(result.package.do_not_claim)} item(s) needing your input."
    )
    yield (
        gr.update(value="", visible=False),
        status,
        _mode_banner(),
        _trace_markdown(result),
        _gaps_markdown(result),
        _feedback_markdown(result),
        result.package.model_dump_json(indent=2),
        gr.update(interactive=True),
        gr.update(interactive=True),
        gr.update(interactive=True),
        result.package.model_dump(),
        "",
    )


def _load_package(state) -> ApplicationPackage | None:
    if not state:
        return None
    try:
        return ApplicationPackage.model_validate(state)
    except Exception:  # noqa: BLE001
        return None


def _current_status(package: ApplicationPackage) -> tuple[ReviewStatus, int]:
    stored = _STORE.get_package(package.package_id)
    if stored:
        return ReviewStatus(stored["status"]), int(stored["revision_count"])
    return ReviewStatus.DRAFT, 0


def approve(state, feedback):
    package = _load_package(state)
    if package is None:
        return gr.update(), "Nothing to approve.", None, _tracker_rows()
    status_now, revisions = _current_status(package)
    try:
        outcome = _REVIEW.apply_decision(
            package,
            ReviewDecision(
                package_id=package.package_id,
                decision=ReviewAction.APPROVE,
                reviewer_feedback=feedback or "",
            ),
            status_now,
            revisions,
        )
    except ReviewError as exc:
        return gr.update(), f"Cannot approve: {exc}", state, _tracker_rows()
    return (
        gr.update(interactive=False),
        f"Package `{package.package_id}` is **{outcome.status.value}**. You can now use it.",
        package.model_dump(),
        _tracker_rows(),
    )


def reject(state, feedback):
    package = _load_package(state)
    if package is None:
        return gr.update(), "Nothing to reject.", None, _tracker_rows()
    status_now, revisions = _current_status(package)
    try:
        _REVIEW.apply_decision(
            package,
            ReviewDecision(
                package_id=package.package_id,
                decision=ReviewAction.REJECT,
                reviewer_feedback=feedback or "",
            ),
            status_now,
            revisions,
        )
    except ReviewError as exc:
        return gr.update(), f"Cannot reject: {exc}", state, _tracker_rows()
    return (
        gr.update(interactive=False),
        f"Package `{package.package_id}` is **REJECTED**.",
        package.model_dump(),
        _tracker_rows(),
    )


def request_revision(state, feedback):
    package = _load_package(state)
    if package is None:
        return gr.update(), state, "Nothing to revise.", None, _tracker_rows()
    if not (feedback or "").strip():
        return gr.update(), state, "Please describe the revision you want.", None, _tracker_rows()
    status_now, revisions = _current_status(package)
    try:
        outcome = _REVIEW.apply_decision(
            package,
            ReviewDecision(
                package_id=package.package_id,
                decision=ReviewAction.REVISE,
                reviewer_feedback=feedback,
            ),
            status_now,
            revisions,
        )
    except ReviewError as exc:
        return gr.update(), state, f"Cannot revise: {exc}", None, _tracker_rows()

    return (
        gr.update(interactive=True),
        state,
        f"Revision {outcome.revision_count} requested. Update the inputs and run again if needed.",
        None,
        _tracker_rows(),
    )


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #
def build_app() -> gr.Blocks:
    with gr.Blocks(title="CareerCrew") as demo:
        state = gr.State(None)

        gr.Markdown(
            "# CareerCrew\n"
            "**A Multi-Agent Resume, Interview, and Job-Application Coach Using CrewAI and MCP**\n\n"
            "Provide a resume and a job description. Five agents extract your profile, "
            "analyze the role, score coverage, draft cited bullets, and assemble an "
            "application package whose screening answers come only from a verified answer bank."
        )
        banner = gr.HTML(_mode_banner())

        with gr.Row():
            with gr.Column(scale=1):
                resume_file = gr.File(label="Resume file (PDF, DOCX, TXT)", file_types=[".pdf", ".docx", ".txt"])
                resume_text = gr.Textbox(
                    label="…or paste resume text",
                    placeholder="Paste the resume text here if you do not have a file.",
                    lines=8,
                )
            with gr.Column(scale=1):
                jd_text = gr.Textbox(
                    label="Job description (paste text)",
                    placeholder="Paste the job description here.",
                    lines=8,
                )
                jd_url = gr.Textbox(
                    label="…or a job description URL (optional, https only)",
                    placeholder="https://example.com/job",
                )
                screening_text = gr.Textbox(
                    label="Screening questions (optional, one per line)",
                    placeholder="Are you authorized to work in the US?\nWhat is your notice period?",
                    lines=5,
                )
                run_btn = gr.Button("Run analysis", variant="primary")

        error_box = gr.Markdown(visible=False)
        status = gr.Markdown("Idle. Provide a resume and a job description, then press **Run analysis**.")

        with gr.Tabs():
            with gr.Tab("Agent workflow"):
                trace_md = gr.Markdown(_trace_markdown(None))
            with gr.Tab("Coverage & gaps"):
                gaps_md = gr.Markdown(_gaps_markdown(None))
            with gr.Tab("Feedback draft"):
                feedback_md = gr.Markdown(_feedback_markdown(None))
            with gr.Tab("Application package"):
                package_json = gr.Code(label="Package JSON", language="json")
            with gr.Tab("Tracker"):
                tracker_table = gr.Dataframe(
                    headers=["Package", "Role", "Company", "Status", "Revisions", "Updated"],
                    datatype=["str"] * 6,
                    interactive=False,
                    label="Packages prepared",
                    value=[],
                )

        gr.Markdown("---\n### Human review")
        feedback = gr.Textbox(
            label="Reviewer feedback (required to request a revision)",
            placeholder="e.g. Drop the AWS bullet, it is not backed by the resume.",
        )
        with gr.Row():
            approve_btn = gr.Button("Approve", interactive=False)
            revise_btn = gr.Button("Request revision", interactive=False)
            reject_btn = gr.Button("Reject", interactive=False)
        review_status = gr.Markdown("")
        refresh_btn = gr.Button("Refresh tracker")

        run_btn.click(
            analyze,
            inputs=[resume_file, resume_text, jd_text, jd_url, screening_text],
            outputs=[
                error_box,
                status,
                banner,
                trace_md,
                gaps_md,
                feedback_md,
                package_json,
                approve_btn,
                reject_btn,
                revise_btn,
                state,
                feedback,
            ],
        ).then(_tracker_rows, outputs=[tracker_table])

        approve_btn.click(
            approve,
            inputs=[state, feedback],
            outputs=[approve_btn, review_status, state, tracker_table],
        )
        reject_btn.click(
            reject,
            inputs=[state, feedback],
            outputs=[reject_btn, review_status, state, tracker_table],
        )
        revise_btn.click(
            request_revision,
            inputs=[state, feedback],
            outputs=[revise_btn, state, review_status, package_json, tracker_table],
        )
        refresh_btn.click(_tracker_rows, outputs=[tracker_table])

    return demo


def main() -> None:
    """Launch the Gradio app bound to 0.0.0.0 for container deployment."""
    app = build_app()
    app.queue().launch(
        server_name="0.0.0.0",
        server_port=_SETTINGS.app_port,
        show_error=True,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    main()
