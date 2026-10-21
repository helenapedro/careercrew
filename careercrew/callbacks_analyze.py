"""Analyze, approve, reject, and request-changes callbacks.

What it does: validates inputs, streams the five-agent run, and records the review decision.
Who calls it: the Analyze tab buttons wired in app.py.
What it returns: ordered Gradio updates (see AnalyzeOutputs).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from collections.abc import Iterator

import gradio as gr

from careercrew import guardrails
from careercrew.models import ApplicationPackage, ReviewAction, ReviewDecision, ReviewStatus
from careercrew.pipeline import AnalysisRequest, make_package_id
from careercrew.runner import FINAL_STAGE as _FINAL
from careercrew.runner import stream_with_progress
from careercrew.services import REVIEW as _REVIEW
from careercrew.services import SETTINGS as _SETTINGS
from careercrew.services import STORE as _STORE
from careercrew.ui_html import (
    _alert_html,
    _insight_html,
    _prep_html,
    _review_guide_html,
    _stages_html,
)
from careercrew.ui_state import AnalyzeOutputs

logger = logging.getLogger("careercrew.app")

_IDLE_STATUS = (
    "Add your resume and the job description, then press **Analyze match**."
)

def _empty_outputs() -> AnalyzeOutputs:
    """The reset state shared by every early return in analyze and request_revision."""
    return AnalyzeOutputs(
        status=_IDLE_STATUS,
        stages=_stages_html(-1),
        match_report=_insight_html(None),
        prep_plan=_prep_html(None),
        review_guide=_review_guide_html("idle"),
    )


def _serialize_result(result) -> str:
    """Serialize the pieces the interview and coach tabs need, as one JSON blob."""
    return json.dumps(
        {
            "package_id": result.package.package_id,
            "profile": result.profile.model_dump(),
            "requirements": result.requirements.model_dump(),
            "gaps": result.gaps.model_dump(),
            "prep_plan": result.prep_plan.model_dump(),
        }
    )


def _load_context(state) -> dict | None:
    """Parse the serialized analysis context, or None when unset/invalid."""
    if not state:
        return None
    try:
        data = json.loads(state) if isinstance(state, str) else state
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _context_models(context: dict) -> dict:
    """Rebuild typed models from a serialized context bundle."""
    return {
        "profile": CandidateProfile.model_validate(context.get("profile") or {}),
        "requirements": JobRequirements.model_validate(context.get("requirements") or {}),
        "gaps": GapReport.model_validate(context.get("gaps") or {}),
        "prep_plan": InterviewPrepPlan.model_validate(context.get("prep_plan") or {}),
        "package_id": context.get("package_id") or "",
    }


# --------------------------------------------------------------------------- #
# Callbacks
# --------------------------------------------------------------------------- #
def _resolve_resume(resume_file, resume_text: str) -> tuple[str | None, str | None]:
    """Copy an uploaded resume into the uploads folder, or use pasted text."""
    return _resolve_upload(resume_file, resume_text, "resume")


def _resolve_upload(upload, pasted: str, kind: str) -> tuple[str | None, str | None]:
    """Copy an uploaded file into the uploads folder, or use pasted text.

    Shared by the resume and job-description inputs so both behave identically.
    """
    if upload:
        # Gradio 6 File may return a path string, a tempfile object, or a 1-item list.
        if isinstance(upload, (list, tuple)):
            upload = upload[0] if upload else None
        if upload is None:
            pass
        else:
            check_name = upload if isinstance(upload, str) else getattr(
                upload, "name", str(upload)
            )
            guardrails.check_upload(check_name)
            os.makedirs(_SETTINGS.upload_dir, exist_ok=True)
            base = os.path.abspath(_SETTINGS.upload_dir)
            destination = os.path.abspath(os.path.join(base, os.path.basename(check_name)))
            if not destination.startswith(base + os.sep):
                raise ValueError(f"invalid {kind} path")
            shutil.copyfile(check_name, destination)
            return os.path.basename(destination), None
    if (pasted or "").strip():
        return None, guardrails.redact_pii(pasted)
    return None, None


def analyze(
    resume_file, resume_text, jd_file, jd_text
) -> Iterator[tuple]:
    """Generator callback: streams live stage progress, then the final results."""
    view = _empty_outputs()

    def fail(message: str, *, status: str = "Couldn’t finish — see the message above.") -> tuple:
        return view.apply(
            error=_alert_html(message, kind="error"),
            status=status,
            stages=_stages_html(-1),
            approve=gr.update(interactive=False),
            reject=gr.update(interactive=False),
            revise=gr.update(interactive=False),
            run_button=gr.update(interactive=True),
            clear_button=gr.update(interactive=True),
        )

    try:
        # Immediate feedback so the click never looks dead; the run button is
        # disabled here and only re-enabled when this generator finishes.
        yield view.apply(
            error="",
            status="**Starting…** checking your resume and job description.",
            stages=_stages_html(1, "Checking your inputs…"),
            run_button=gr.update(interactive=False),
            clear_button=gr.update(interactive=False),
        )

        # --- Stage 1: input guardrails (resume + JD resolution). ------------ #
        try:
            resume_path, pasted_resume = _resolve_resume(resume_file, resume_text)
        except Exception as exc:  # noqa: BLE001 - surface a clean error
            yield fail(f"Resume error: {exc}", status="Resume rejected.")
            return

        if resume_path is None and pasted_resume is None:
            yield fail(
                "Add a resume first — upload a PDF/DOCX/TXT file, or paste the text "
                "in the Paste text tab."
            )
            return

        try:
            jd_path, pasted_jd = _resolve_upload(jd_file, jd_text, "job description")
        except Exception as exc:  # noqa: BLE001 - surface a clean error
            yield fail(f"Job description error: {exc}", status="Job description rejected.")
            return

        if jd_path is None and pasted_jd is None:
            yield fail(
                "Add a job description — upload a PDF/DOCX/TXT file, or paste the "
                "posting text in the Paste posting tab."
            )
            return

        # Seniority is inferred from the JD inside the pipeline (no UI picker).
        request = AnalysisRequest(
            package_id=make_package_id(),
            resume_path=resume_path,
            resume_text=pasted_resume,
            jd_path=jd_path,
            jd_text=pasted_jd,
            seniority="",
        )

        yield view.apply(
            error="",
            status="Checking your inputs…",
            stages=_stages_html(1, "Checking that your resume and job description look valid"),
        )

        stages_run = stream_with_progress(request, reading_detail="Reading your resume…")
        try:
            while True:
                try:
                    target, detail = next(stages_run)
                except StopIteration as finished:
                    result = finished.value
                    break
                yield view.apply(stages=_stages_html(target, detail), status=detail)
        except Exception as exc:  # noqa: BLE001 - surface a clean error, never crash
            logger.exception("analysis run failed")
            yield fail(str(exc) or "Analysis failed unexpectedly.")
            return

        _REVIEW.submit_for_review(
            {
                "resume_path": request.resume_path,
                "resume_text": request.resume_text,
                "jd_path": request.jd_path,
                "jd_text": request.jd_text,
                "seniority": request.seniority,
            },
            result.package,
            result.trace,
        )

        mode = " (limited mode)" if result.used_fallback else ""
        status = (
            f"**Your prep bundle is ready{mode}.** "
            f"`{result.package.package_id}` · "
            f"{len(result.prep_plan.focus_areas)} prep focus area(s) · "
            f"{len(result.package.do_not_claim)} item(s) still need your input."
        )
        yield view.apply(
            error="",
            status=status,
            stages=_stages_html(_FINAL, "All set — review your match report, prep plan, and answers."),
            match_report=_insight_html(result),
            prep_plan=_prep_html(result.prep_plan),
            approve=gr.update(interactive=True),
            reject=gr.update(interactive=True),
            revise=gr.update(interactive=True),
            package=result.package.model_dump(),
            notes=gr.update(value="", interactive=True),
            context=_serialize_result(result),
            review_guide=_review_guide_html("ready", package_id=result.package.package_id),
            run_button=gr.update(interactive=True),
            clear_button=gr.update(interactive=True),
        )
    except Exception as exc:  # noqa: BLE001 - never let Gradio swallow a silent failure
        logger.exception("analyze callback crashed")
        yield fail(f"Unexpected error: {exc}")


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
    """Returns the shared decision-dock outputs (guide + buttons + status…)."""
    package = _load_package(state)
    if package is None:
        return (
            _review_guide_html("idle"),
            gr.update(),
            gr.update(),
            gr.update(),
            "Nothing to approve — run Analyze first.",
            None,
            gr.update(),
        )
    status_now, revisions = _current_status(package)
    try:
        _REVIEW.apply_decision(
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
        return (
            _review_guide_html("ready", package_id=package.package_id),
            gr.update(),
            gr.update(),
            gr.update(),
            f"Cannot approve: {exc}",
            state,
            gr.update(),
        )
    return (
        _review_guide_html("approved", package_id=package.package_id),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        f"Approved — prep bundle `{package.package_id}` is ready to use. "
        "Next: open **Interview prep plan**, **Prep coach**, or **Mock interview**.",
        package.model_dump(),
        gr.update(value="", interactive=False),
    )


def reject(state, feedback):
    package = _load_package(state)
    if package is None:
        return (
            _review_guide_html("idle"),
            gr.update(),
            gr.update(),
            gr.update(),
            "Nothing to reject — run Analyze first.",
            None,
            gr.update(),
        )
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
        return (
            _review_guide_html("ready", package_id=package.package_id),
            gr.update(),
            gr.update(),
            gr.update(),
            f"Cannot reject: {exc}",
            state,
            gr.update(),
        )
    return (
        _review_guide_html("rejected", package_id=package.package_id),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        f"Rejected — prep bundle `{package.package_id}` will not be used.",
        package.model_dump(),
        gr.update(value="", interactive=False),
    )


def _merge_revision_into_resume(
    resume_path: str | None, resume_text: str | None, notes: str
) -> str:
    """Fold candidate-attested Request-changes notes into the resume text.

    Agents then re-extract the profile and re-score gaps so new experience
    (e.g. React years) updates the match report, prep plan, and rewrites.
    """
    base = (resume_text or "").strip()
    if not base and resume_path:
        try:
            from careercrew.document_tools import read_resume

            base = (read_resume(resume_path) or "").strip()
        except Exception:  # noqa: BLE001 - fall back to notes-only addendum
            logger.warning("could not re-read resume %s for revision", resume_path, exc_info=True)
            base = ""
    block = (
        "\n\n---\n"
        "CANDIDATE-ATTESTED UPDATE (from Request changes):\n"
        "Treat the following as real experience the candidate confirms they have, "
        "even if it was missing from the original resume. Use it when scoring "
        "coverage, writing bullets, and planning interview prep.\n"
        f"{notes.strip()}\n"
    )
    return f"{base}{block}".strip() if base else notes.strip()


def request_revision(state, feedback) -> Iterator[tuple]:
    """Merge candidate experience updates, re-analyze, and refresh every result tab.

    ``Request changes`` is how the candidate adds missing experience (e.g. React
    years not on the resume). Notes are folded into the resume context and the
    full Analyze pipeline runs again so gaps, prep, and answers update.
    """
    view = _empty_outputs()
    package = _load_package(state)

    def fail(message: str) -> tuple:
        return view.apply(
            error=_alert_html(message, kind="error"),
            status="Revision could not finish — see the message above.",
            stages=_stages_html(-1),
            approve=gr.update(interactive=bool(package)),
            reject=gr.update(interactive=bool(package)),
            revise=gr.update(interactive=bool(package)),
            package=state,
            notes=gr.update(interactive=bool(package)),
            run_button=gr.update(interactive=True),
            clear_button=gr.update(interactive=True),
            review_guide=_review_guide_html(
                "ready" if package else "idle",
                package_id=package.package_id if package else "",
            ),
        )

    if package is None:
        yield fail("Nothing to revise — run Analyze first.")
        return

    notes = (feedback or "").strip()
    if not notes:
        yield fail(
            "Describe the experience or corrections to apply "
            "(e.g. “I have 5+ years of React experience”)."
        )
        return

    status_now, revisions = _current_status(package)
    try:
        outcome = _REVIEW.apply_decision(
            package,
            ReviewDecision(
                package_id=package.package_id,
                decision=ReviewAction.REVISE,
                reviewer_feedback=notes,
            ),
            status_now,
            revisions,
        )
    except ReviewError as exc:
        yield fail(f"Cannot revise: {exc}")
        return

    stored = _STORE.get_package(package.package_id) or {}
    saved = stored.get("inputs") or {}
    resume_path = saved.get("resume_path") or None
    resume_text = saved.get("resume_text") or None
    jd_path = saved.get("jd_path") or None
    jd_text = saved.get("jd_text") or None
    if not resume_path and not resume_text:
        yield fail(
            "Saved resume inputs are missing for this prep bundle. "
            "Update the resume/JD fields and press Analyze match again."
        )
        return
    if not jd_path and not jd_text:
        yield fail(
            "Saved job-description inputs are missing for this prep bundle. "
            "Update the resume/JD fields and press Analyze match again."
        )
        return

    # Fold notes into resume text so profile → gaps → prep all see the new experience.
    updated_resume = _merge_revision_into_resume(resume_path, resume_text, notes)
    request = AnalysisRequest(
        package_id=package.package_id,
        resume_path=None,
        resume_text=updated_resume,
        jd_path=jd_path,
        jd_text=jd_text,
        seniority=saved.get("seniority") or "",
        revision_notes=notes,
    )

    yield view.apply(
        error="",
        status=(
            f"**Revision {outcome.revision_count}…** updating your experience from the "
            "notes and re-analyzing the match."
        ),
        stages=_stages_html(1, "Merging your experience updates…"),
        approve=gr.update(interactive=False),
        reject=gr.update(interactive=False),
        revise=gr.update(interactive=False),
        package=state,
        notes=gr.update(value=notes, interactive=False),
        review_guide=_review_guide_html(
            "working",
            package_id=package.package_id,
            detail="Analyze is running again with your experience updates…",
        ),
        run_button=gr.update(interactive=False),
        clear_button=gr.update(interactive=False),
    )

    stages_run = stream_with_progress(request, reading_detail="Re-reading your resume…")
    try:
        while True:
            try:
                target, detail = next(stages_run)
            except StopIteration as finished:
                result = finished.value
                break
            yield view.apply(stages=_stages_html(target, detail), status=detail)
    except Exception as exc:  # noqa: BLE001
        logger.exception("revision re-run failed")
        yield fail(str(exc) or "Revision re-run failed unexpectedly.")
        return

    try:
        _REVIEW.submit_for_review(
            {
                "resume_path": request.resume_path,
                "resume_text": request.resume_text,
                "jd_path": request.jd_path,
                "jd_text": request.jd_text,
                "seniority": request.seniority,
            },
            result.package,
            result.trace,
            revision_count=outcome.revision_count,
        )

        mode = " (limited mode)" if result.used_fallback else ""
        status = (
            f"**Revision {outcome.revision_count} is ready{mode}.** "
            f"Your experience updates were merged and the match / prep / answers "
            f"were rebuilt — `{result.package.package_id}`. Review the updated tabs, "
            f"then approve, add more experience, or reject."
        )
        yield view.apply(
            error="",
            status=status,
            stages=_stages_html(_FINAL, "Experience updated — review the new match report."),
            match_report=_insight_html(result),
            prep_plan=_prep_html(result.prep_plan),
            approve=gr.update(interactive=True),
            reject=gr.update(interactive=True),
            revise=gr.update(interactive=True),
            package=result.package.model_dump(),
            notes=gr.update(value="", interactive=True),
            context=_serialize_result(result),
            review_guide=_review_guide_html("ready", package_id=result.package.package_id),
            run_button=gr.update(interactive=True),
            clear_button=gr.update(interactive=True),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("request_revision crashed")
        yield fail(f"Unexpected error: {exc}")

