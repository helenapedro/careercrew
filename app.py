"""CareerCrew - candidate-facing Gradio product UI.

Plain-language workflow for job seekers:

1. Add a resume (upload or paste) and a job description (upload or paste).
2. Optionally add screening questions.
3. Press **Analyze match** and watch live progress.
4. Review coverage, rewrite suggestions, an interview prep plan (calibrated to
   the seniority signaled in the JD), and copy-ready screening answers
   (nothing is submitted anywhere).
5. Practice with the voice mock interviewer, then chat with the prep coach and
   the post-interview coach.

Technical details (agents, MCP, JSON, traces) live under **Advanced**.
Screening answers come only from a verified answer bank; unverified questions
are surfaced for the candidate instead of being invented.
"""

from __future__ import annotations

import html
import json
import logging
import os
import shutil
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as _wait_futures

import gradio as gr

from careercrew import audio, coach, guardrails, interview, llm
from careercrew.config import get_settings
from careercrew.models import (
    AnswerEvaluation,
    CandidateProfile,
    GapReport,
    InterviewPrepPlan,
    InterviewQuestion,
    InterviewTurnRole,
    JobRequirements,
    MockInterviewSession,
    ReviewAction,
    ReviewDecision,
    ReviewStatus,
    ScreeningPrep,
)
from careercrew.pipeline import AnalysisRequest, make_package_id, run_analysis
from careercrew.review import PackageReviewService, ReviewError
from careercrew.session_store import SessionStore
from careercrew.ui_css import CUSTOM_CSS

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger("careercrew.app")

_SETTINGS = get_settings()
_STORE = SessionStore(_SETTINGS.db_path)
_REVIEW = PackageReviewService(_STORE)

os.makedirs(_SETTINGS.upload_dir, exist_ok=True)
_SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")

_IDLE_STATUS = (
    "Add your resume and the job description, then press **Analyze match**."
)

# --------------------------------------------------------------------------- #
# Pipeline stages — candidate-facing labels (backend stages stay the same)
# --------------------------------------------------------------------------- #
STAGES: list[tuple[int, str, str]] = [
    (1, "Check inputs", "Make sure your resume and job posting look valid"),
    (2, "Read resume", "Pull out skills, roles, and achievements from your resume"),
    (3, "Understand role", "Extract what the job actually requires"),
    (4, "Score match", "Mark each requirement as covered, reframeable, or out of scope"),
    (5, "Draft rewrites", "Suggest stronger bullets backed by facts from your resume"),
    (6, "Prep plan", "Plan where to spend your interview preparation time"),
    (7, "Screening + check", "Prepare copy-ready answers and verify honesty rules"),
]
_TOTAL_STAGES = len(STAGES)
_FINAL = _TOTAL_STAGES + 1  # sentinel: marks every stage complete

#: Map CrewAI agent names to the stage they belong to, for live progress.
_AGENT_STAGE = {
    "Profile Extractor": 2,
    "JD Analyzer": 3,
    "Gap Analyst": 4,
    "Feedback Writer": 5,
    "Interview Prep Advisor": 6,
    "Screening Answer Prep Writer": 7,
}
_TASK_STAGE = {
    "extract_profile": 2,
    "analyze_jd": 3,
    "analyze_gaps": 4,
    "write_feedback": 5,
    "build_prep_plan": 6,
    "prepare_screening_answers": 7,
}

# --------------------------------------------------------------------------- #
# Small rendering helpers
# --------------------------------------------------------------------------- #
def _esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""))


def _alert_html(message: str = "", *, kind: str = "error") -> str:
    """Always-mounted alert under the CTA. Empty string clears it."""
    text = (message or "").strip()
    if not text:
        return ""
    return (
        f"<div class='cc-alert {kind}' role='alert'>"
        f"<strong>{'Something went wrong' if kind == 'error' else 'Working'}</strong>"
        f"{_esc(text)}</div>"
    )


def _mode_banner() -> str:
    if _SETTINGS.has_llm:
        return (
            "<div class='cc-status-chip'><span class='dot'></span>"
            "Full analysis ready — your match, rewrites, and package will be prepared</div>"
        )
    return (
        "<div class='cc-status-chip warn'><span class='dot'></span>"
        "Limited mode — screening answers still work; add an API key for the full match report</div>"
    )


def _topbar() -> str:
    chip = (
        "<div class='cc-status-chip'><span class='dot'></span>Ready</div>"
        if _SETTINGS.has_llm
        else "<div class='cc-status-chip warn'><span class='dot'></span>Limited mode</div>"
    )
    return (
        "<div class='cc-topbar'>"
        "<div class='cc-brand'>"
        "<div class='cc-mark'>C</div>"
        "<div><div class='cc-brand-name'>CareerCrew</div>"
        "<div class='cc-brand-tag'>Resume &amp; application coach</div></div>"
        f"</div>{chip}</div>"
    )


def _hero() -> str:
    return (
        "<div class='cc-hero'>"
        "<h1>Match your resume to the role</h1>"
        "<p class='cc-sub'>Use the tabs below in order: analyze the match, practice the interview, "
        "then chat with a coach. Progress and decisions stay inside Analyze — they won’t clutter "
        "the other steps.</p>"
        "<div class='cc-trust'>"
        "<span>1 · Analyze match</span>"
        "<span>2 · Mock interview</span>"
        "<span>3 · Coaches</span>"
        "</div></div>"
    )


def _stages_html(current: int = -1, detail: str = "") -> str:
    """Render the live progress stepper.

    ``current`` is the stage number that is executing: lower numbers are done,
    the current one is active, higher numbers are queued. ``current`` greater
    than the number of stages marks everything complete; ``-1`` means idle.
    """
    rows: list[str] = []
    for number, title, blurb in STAGES:
        if current < 0:
            cls, icon, pill = "", str(number), "READY"
        elif number < current:
            cls, icon, pill = "done", "✓", "DONE"
        elif number == current:
            cls, icon, pill = "active", str(number), "RUNNING"
        else:
            cls, icon, pill = "", str(number), "QUEUED"
        rows.append(
            f"<div class='cc-stage {cls}' title='{_esc(blurb)}'>"
            f"<div class='cc-dot'>{icon}</div>"
            f"<div class='cc-ttl'>{_esc(title)}</div>"
            f"<div class='cc-blurb'>{_esc(blurb)}</div>"
            f"<div class='cc-pill'>{pill}</div>"
            "</div>"
        )
    live = ""
    if detail:
        live = (
            "<div class='cc-live'><span class='cc-blink'>●</span>"
            f"<span>{_esc(detail)}</span></div>"
        )
    shown = 0 if current < 0 else min(current, _TOTAL_STAGES)
    if current >= _FINAL:
        shown = _TOTAL_STAGES
    header = (
        "<div class='cc-card cc-progress'>"
        "<div class='cc-progress-top'>"
        "<div><h3 style='margin:0'>Analyze progress</h3>"
        "<div class='cc-progress-label'>Runs only while this match is being prepared.</div></div>"
        f"<div class='cc-progress-count'>{shown} / {_TOTAL_STAGES}</div>"
        "</div><div class='cc-stages'>"
    )
    return header + "".join(rows) + "</div>" + live + "</div>"


def _empty_card(title: str, hint: str) -> str:
    return (
        f"<div class='cc-card'><h3>{_esc(title)}</h3>"
        f"<div class='cc-empty'><strong>Nothing here yet</strong>{_esc(hint)}</div></div>"
    )


def _trace_markdown(result) -> str:
    if not result:
        return (
            "**Advanced — what ran behind the scenes**\n\n"
            "After you analyze a match, this tab shows the detailed step log "
            "(useful for debugging or class demos)."
        )
    marker = {"ok": "PASS", "warning": "WARN", "error": "FAIL"}
    lines = ["**Execution trace**", ""]
    for event in result.trace.events:
        tag = marker.get(event.status, event.status.upper())
        duration = f" · {event.duration_ms} ms" if event.duration_ms is not None else ""
        lines.append(f"- `{tag}` **{event.step}** — {event.detail}{duration}")
    if result.warnings:
        lines.append("\n**Warnings**")
        lines.extend(f"- {warning}" for warning in result.warnings)
    return "\n".join(lines)


def _verdict_class(verdict: str) -> str:
    key = (verdict or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key.startswith("reframe"):
        return "reframeable"
    if key.startswith("out"):
        return "out"
    return "covered"


def _insight_html(result) -> str:
    """Coverage meter, profile, requirements, gap verdicts, and the rewrite plan."""
    if not result:
        return _empty_card(
            "Your match report",
            "Analyze a match to see your coverage score, which requirements you already meet, "
            "and suggested resume rewrites backed by your experience.",
        )

    gaps = result.gaps
    score = max(0, min(100, int(gaps.coverage_score)))
    verdicts = gaps.verdicts
    counts = {"covered": 0, "reframeable": 0, "out": 0}
    for verdict in verdicts:
        counts[_verdict_class(verdict.verdict)] += 1

    parts: list[str] = ["<div class='cc-card'>"]
    parts.append("<h3>Your match score</h3>")
    parts.append(
        "<p class='cc-hint'>How much of this role’s requirements your resume already supports — "
        "without inventing experience.</p>"
    )
    label = "Based on the job requirements" if verdicts else "Waiting for requirement details"
    parts.append(
        "<div class='cc-meter'>"
        "<div class='cc-meter-top'>"
        f"<div class='cc-score'>{score}<small>/100</small></div>"
        f"<div class='cc-meter-label'>{label}</div>"
        "</div>"
        f"<div class='cc-bar'><span style='width:{score}%'></span></div>"
        "<div class='cc-stats'>"
        f"<span class='cc-chip covered'>✓ covered · {counts['covered']}</span>"
        f"<span class='cc-chip reframeable'>~ reframeable · {counts['reframeable']}</span>"
        f"<span class='cc-chip out'>✕ out of scope · {counts['out']}</span>"
        "</div></div>"
    )

    profile = result.profile
    if profile.full_name or profile.skills or profile.experience:
        parts.append("<div class='cc-section-title'>From your resume</div>")
        if profile.full_name:
            parts.append(f"<div style='font-weight:700;font-size:15px'>{_esc(profile.full_name)}</div>")
        if profile.summary:
            parts.append(
                f"<p style='color:var(--cc-ink-2);font-size:13.5px;margin:6px 0;line-height:1.55'>{_esc(profile.summary)}</p>"
            )
        if profile.skills:
            chips = "".join(f"<span class='cc-chip'>{_esc(skill)}</span>" for skill in profile.skills)
            parts.append(f"<div class='cc-stats'>{chips}</div>")
        for role in profile.experience:
            line = " · ".join(x for x in [role.title, role.company, role.dates] if x)
            if line:
                parts.append(
                    f"<p style='font-size:13px;color:var(--cc-ink-2);margin:8px 0 0 0'>• {_esc(line)}</p>"
                )

    reqs = result.requirements
    if reqs.required_skills or reqs.keywords or reqs.seniority:
        parts.append("<div class='cc-section-title'>What the role asks for</div>")
        if reqs.seniority:
            parts.append(
                f"<div class='cc-stats'><span class='cc-chip'>seniority · {_esc(reqs.seniority)}</span></div>"
            )
        if reqs.required_skills:
            chips = "".join(
                f"<span class='cc-badge src'>{_esc(skill)}</span>" for skill in reqs.required_skills
            )
            parts.append(f"<div class='cc-stats'>{chips}</div>")

    if verdicts:
        parts.append("<div class='cc-section-title'>Requirement by requirement</div>")
        parts.append(
            "<table class='cc-table'><thead><tr><th>Requirement</th><th>Status</th>"
            "<th>Evidence from your resume</th></tr></thead><tbody>"
        )
        for verdict in verdicts:
            cls = _verdict_class(verdict.verdict)
            parts.append(
                "<tr>"
                f"<td>{_esc(verdict.requirement)}</td>"
                f"<td><span class='cc-badge {cls}'>{_esc(verdict.verdict.upper())}</span></td>"
                f"<td>{_esc(verdict.supporting_fact) or '—'}</td>"
                "</tr>"
            )
        parts.append("</tbody></table>")

    feedback = result.feedback
    if feedback.rewritten_bullets:
        n = len(feedback.rewritten_bullets)
        parts.append(
            "<div class='cc-section-title'>Suggested resume rewrites"
            f"<span class='cc-count'>{n}</span></div>"
            "<p class='cc-section-lead'>Stronger bullets grounded in facts already on your resume.</p>"
        )
        bullets = "".join(
            "<li>"
            f"<span class='cc-idx'>{idx}</span>"
            "<div class='cc-bullet-body'>"
            f"<p>{_esc(bullet.text)}</p>"
            "<div class='cc-cite'>"
            "<span class='cc-cite-label'>Based on</span>"
            f"<span class='cc-cite-fact'>{_esc(bullet.cited_fact) or '—'}</span>"
            "</div>"
            "</div>"
            "</li>"
            for idx, bullet in enumerate(feedback.rewritten_bullets, start=1)
        )
        parts.append(f"<ul class='cc-bullets'>{bullets}</ul>")

    if feedback.talking_points:
        n = len(feedback.talking_points)
        parts.append(
            "<div class='cc-section-title'>Interview talking points"
            f"<span class='cc-count'>{n}</span></div>"
            "<p class='cc-section-lead'>Stories and angles to practice saying out loud.</p>"
        )
        items = "".join(
            "<li>"
            f"<span class='cc-idx'>{idx}</span>"
            f"<div class='cc-talk-text'>{_esc(point)}</div>"
            "</li>"
            for idx, point in enumerate(feedback.talking_points, start=1)
        )
        parts.append(f"<ul class='cc-talks'>{items}</ul>")

    if feedback.do_not_claim:
        n = len(feedback.do_not_claim)
        items = "".join(f"<li>{_esc(item)}</li>" for item in feedback.do_not_claim)
        parts.append(
            "<div class='cc-section-title'>Do not claim"
            f"<span class='cc-count'>{n}</span></div>"
            "<div class='cc-caution'>"
            "<div class='cc-caution-head'><span class='cc-caution-mark'>!</span>"
            "Leave these off your resume and interview answers</div>"
            "<p class='cc-caution-lead'>These requirements are not backed by your resume. "
            "Claiming them would invent qualifications CareerCrew is designed to prevent.</p>"
            f"<ul class='cc-list'>{items}</ul>"
            "</div>"
        )

    parts.append("</div>")
    return "".join(parts)


def _package_html(package: ScreeningPrep | None, warnings: list[str] | None = None) -> str:
    """Candidate-facing copy-ready screening answers + items needing input."""
    if package is None:
        return _empty_card(
            "Copy-ready screening answers",
            "After analysis, you’ll see verified answers you can paste into your own "
            "application — and anything that still needs your personal input. "
            "Nothing is submitted for you.",
        )

    parts = ["<div class='cc-card'>"]
    parts.append("<h3>Copy-ready screening answers</h3>")
    role = package.role_title or "Role"
    company = package.company or "Company"
    parts.append(
        f"<p class='cc-hint'><span class='cc-badge ghost'>{_esc(package.package_id)}</span> "
        f"{_esc(role)} · {_esc(company)}</p>"
    )
    parts.append(
        "<div class='cc-alert info'><strong>Nothing is submitted</strong>"
        "These are answers you can copy into your own application. CareerCrew never "
        "applies on your behalf.</div>"
    )
    if package.package_summary:
        parts.append(f"<p style='color:var(--cc-ink-2);font-size:14px;line-height:1.55'>{_esc(package.package_summary)}</p>")

    parts.append(f"<div class='cc-section-title'>Screening answers ({len(package.screening_answers)})</div>")
    if package.screening_answers:
        parts.append("<div class='cc-qa'>")
        for answer in package.screening_answers:
            parts.append(
                "<div class='cc-qa-item'>"
                f"<p class='cc-q'>{_esc(answer.question)}</p>"
                f"<p class='cc-a'>{_esc(answer.answer)}</p>"
                "<span class='cc-badge on'>Verified answer</span>"
                "</div>"
            )
        parts.append("</div>")
    else:
        parts.append(
            "<div class='cc-empty'>No screening questions were answered yet. "
            "Add questions above and analyze again.</div>"
        )

    if package.do_not_claim:
        n = len(package.do_not_claim)
        items = "".join(f"<li>{_esc(item)}</li>" for item in package.do_not_claim)
        parts.append(
            f"<div class='cc-section-title'>Needs your input<span class='cc-count'>{n}</span></div>"
            "<div class='cc-caution'>"
            "<div class='cc-caution-head'><span class='cc-caution-mark'>!</span>"
            "Answer these yourself</div>"
            "<p class='cc-caution-lead'>We won’t invent answers for these. "
            "Fill them in from your own facts before you apply.</p>"
            f"<ul class='cc-list'>{items}</ul>"
            "</div>"
        )

    if warnings:
        notes = "".join(f"<li>{_esc(w)}</li>" for w in warnings)
        parts.append(
            f"<div class='cc-section-title'>Notes</div><ul class='cc-list'>{notes}</ul>"
        )

    parts.append("</div>")
    return "".join(parts)


def _priority_class(priority: str) -> str:
    key = (priority or "").strip().lower()
    if key == "high":
        return "out"
    if key == "medium":
        return "reframeable"
    return "covered"


def _prep_html(plan: InterviewPrepPlan | None) -> str:
    """Render the seniority-aware interview preparation plan."""
    if plan is None or (not plan.focus_areas and not plan.seniority.rationale):
        return _empty_card(
            "Interview prep plan",
            "After analysis, you’ll see which parts of the role to spend the most "
            "preparation time on, based on your gaps and the seniority signaled in the job posting.",
        )

    parts = ["<div class='cc-card'>"]
    parts.append("<h3>Interview prep plan</h3>")
    seniority = plan.seniority
    parts.append(
        "<div class='cc-stats'>"
        f"<span class='cc-chip'>target · {_esc(seniority.target_years or seniority.band.label)}</span>"
        f"<span class='cc-chip'>confidence · {int(seniority.confidence)}%</span>"
        f"<span class='cc-chip'>detected · {_esc(seniority.detected_years) or '—'}</span>"
        "</div>"
    )
    if seniority.rationale:
        parts.append(
            f"<p class='cc-hint' style='margin-top:10px'>{_esc(seniority.rationale)}</p>"
        )

    if plan.focus_areas:
        parts.append("<div class='cc-section-title'>Where to spend your time</div>")
        parts.append("<div class='cc-qa'>")
        for focus in plan.focus_areas:
            cls = _priority_class(focus.priority)
            parts.append(
                "<div class='cc-qa-item'>"
                f"<p class='cc-q'>{_esc(focus.area)} "
                f"<span class='cc-badge {cls}'>{_esc(focus.priority.upper())}</span> "
                f"<span class='cc-badge src'>{int(focus.suggested_share_pct)}% of prep time</span></p>"
                f"<p class='cc-a'>{_esc(focus.why)}</p>"
                "<div class='cc-cite'>"
                "<span class='cc-cite-label'>Grounded in</span>"
                f"<span class='cc-cite-fact'>{_esc(focus.evidence) or '—'}</span>"
                "</div>"
                "</div>"
            )
        parts.append("</div>")

    if plan.question_themes:
        parts.append("<div class='cc-section-title'>Question themes to practice</div>")
        items = "".join(f"<li>{_esc(theme)}</li>" for theme in plan.question_themes)
        parts.append(f"<ul class='cc-list'>{items}</ul>")

    if plan.strengths:
        parts.append("<div class='cc-section-title'>Your strengths</div>")
        chips = "".join(f"<span class='cc-chip covered'>{_esc(s)}</span>" for s in plan.strengths)
        parts.append(f"<div class='cc-stats'>{chips}</div>")

    if plan.risk_areas:
        parts.append("<div class='cc-section-title'>Highest-risk areas</div>")
        items = "".join(f"<li>{_esc(r)}</li>" for r in plan.risk_areas)
        parts.append(f"<div class='cc-note'><ul class='cc-list'>{items}</ul></div>")

    parts.append("</div>")
    return "".join(parts)


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


def _review_guide_html(
    phase: str = "idle", *, package_id: str = "", detail: str = ""
) -> str:
    """Step-by-step guide for the HITL decision dock.

    ``phase``: idle | ready | working | approved | rejected
    """
    steps = [
        (1, "Upload resume + JD above, then press Analyze match"),
        (2, "Open the result sub-tabs (Match / Prep / Screening)"),
        (3, "Decide below — approve, add missing experience, or reject"),
    ]
    if phase == "idle":
        active = 1
        blurb = (
            "Unlocks after Analyze finishes in this tab. "
            "Nothing here is submitted to an employer."
        )
    elif phase == "working":
        active = 3
        blurb = detail or (
            "Applying your experience updates and re-running Analyze automatically…"
        )
    elif phase == "approved":
        active = 3
        blurb = (
            f"Approved{f' — `{_esc(package_id)}`' if package_id else ''}. "
            "Next: Interview prep plan, Mock interview, or Prep coach."
        )
    elif phase == "rejected":
        active = 3
        blurb = (
            f"Rejected{f' — `{_esc(package_id)}`' if package_id else ''}. "
            "Adjust inputs above and Analyze again if you want a new bundle."
        )
    else:  # ready
        active = 3
        blurb = (
            f"Prep bundle ready{f' (`{_esc(package_id)}`)' if package_id else ''}. "
            "Choose <strong>A</strong>, <strong>B</strong>, or <strong>C</strong> below."
        )

    rows: list[str] = []
    for number, title in steps:
        if number < active:
            cls, pill = "done", "DONE"
        elif number == active:
            cls, pill = "active", "NOW"
        else:
            cls, pill = "", "NEXT"
        rows.append(
            f"<div class='cc-review-step {cls}'>"
            f"<span class='cc-review-step-n'>{number}</span>"
            f"<span class='cc-review-step-t'>{_esc(title)}</span>"
            f"<span class='cc-review-step-pill'>{pill}</span></div>"
        )
    return (
        "<div class='cc-panel-head'><h3>Your decision</h3>"
        f"<p class='cc-hint'>{blurb}</p></div>"
        f"<div class='cc-review-steps'>{''.join(rows)}</div>"
    )


def _empty_outputs() -> tuple:
    """The reset state shared by every early return in :func:`analyze`."""
    return (
        "",  # error_box (HTML alert; empty = hidden)
        _IDLE_STATUS,  # status
        _mode_banner(),  # banner
        _stages_html(-1),  # stages_html
        _trace_markdown(None),  # trace_md
        _insight_html(None),  # insight_html
        _prep_html(None),  # prep_html
        _package_html(None),  # package_md (HTML package view)
        "",  # package_json
        gr.update(interactive=False),  # approve_btn
        gr.update(interactive=False),  # reject_btn
        gr.update(interactive=False),  # revise_btn
        None,  # state
        gr.update(value="", interactive=False),  # review_feedback
        _tracker_rows(),  # tracker_table
        None,  # context_state (JSON bundle for interview + coach tabs)
        _review_guide_html("idle"),  # review_guide_html
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
    resume_file, resume_text, jd_file, jd_text, screening_text
) -> Iterator[tuple]:
    """Generator callback: streams live stage progress, then the final results."""
    outputs = list(_empty_outputs())

    def emit(*pairs) -> tuple:
        """Mutate and return the full output tuple from ``index, value`` pairs."""
        for position in range(0, len(pairs), 2):
            outputs[pairs[position]] = pairs[position + 1]
        return tuple(outputs)

    def fail(message: str, *, status: str = "Couldn’t finish — see the message above.") -> tuple:
        return emit(
            0, _alert_html(message, kind="error"),
            1, status,
            3, _stages_html(-1),
            9, gr.update(interactive=False),
            10, gr.update(interactive=False),
            11, gr.update(interactive=False),
        )

    try:
        # Immediate feedback so the click never looks dead.
        yield emit(
            0, "",
            1, "**Starting…** checking your resume and job description.",
            3, _stages_html(1, "Checking your inputs…"),
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

        questions = [line.strip() for line in (screening_text or "").splitlines() if line.strip()]
        # Seniority is inferred from the JD inside the pipeline (no UI picker).
        request = AnalysisRequest(
            package_id=make_package_id(),
            resume_path=resume_path,
            resume_text=pasted_resume,
            jd_path=jd_path,
            jd_text=pasted_jd,
            seniority="",
            screening_questions=questions,
        )

        yield emit(
            0, "",
            1, "Checking your inputs…",
            3, _stages_html(1, "Checking that your resume and job description look valid"),
        )

        stages: dict[str, object] = {"index": 1, "detail": "Checking your inputs…"}

        def progress(message: str) -> None:
            """Bridge the pipeline's progress messages onto the stage tracker."""
            lowered = message.lower()
            if "crew output unavailable" in lowered or "direct mcp calls" in lowered:
                stages["index"], stages["detail"] = 7, "Preparing screening answers from your verified bank…"
            elif "six-agent crew" in lowered:
                stages["index"], stages["detail"] = 2, "Reading your resume…"
            else:
                stages["detail"] = message

        def on_task(output) -> None:
            """CrewAI task callback: refine the tracker after each task completes."""
            name = getattr(output, "name", "") or ""
            agent = getattr(output, "agent", "") or ""
            stage = _AGENT_STAGE.get(agent) or _TASK_STAGE.get(name)
            if stage:
                title = next((t for n, t, _ in STAGES if n == stage), name or agent)
                stages["index"] = stage + 1
                stages["detail"] = f"Finished: {title}"

        def advance(stage_index: int, label: str) -> tuple:
            return emit(3, _stages_html(stage_index, label), 1, label)

        # run_analysis blocks, so run it on a worker thread and poll for progress.
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run_analysis, request, progress=progress, on_task=on_task)

            expected = 2
            last_yielded = 1
            while not future.done():
                reported = int(stages["index"])
                if reported >= expected:
                    expected = reported + 1
                target = min(expected, _TOTAL_STAGES)
                if target != last_yielded:
                    last_yielded = target
                    detail = str(stages["detail"] or "Working…")
                    yield advance(target, f"{detail}")
                _wait_futures([future], timeout=1.0)

            try:
                result = future.result()
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
                "screening_questions": request.screening_questions,
            },
            result.package,
            result.trace,
        )

        mode = " (limited mode)" if result.used_fallback else ""
        status = (
            f"**Your prep bundle is ready{mode}.** "
            f"`{result.package.package_id}` · "
            f"{len(result.package.screening_answers)} verified answer(s) · "
            f"{len(result.prep_plan.focus_areas)} prep focus area(s) · "
            f"{len(result.package.do_not_claim)} item(s) still need your input."
        )
        yield emit(
            0, "",
            1, status,
            3, _stages_html(_FINAL, "All set — review your match report, prep plan, and answers."),
            4, _trace_markdown(result),
            5, _insight_html(result),
            6, _prep_html(result.prep_plan),
            7, _package_html(result.package, result.warnings),
            8, result.package.model_dump_json(indent=2),
            9, gr.update(interactive=True),
            10, gr.update(interactive=True),
            11, gr.update(interactive=True),
            12, result.package.model_dump(),
            13, gr.update(value="", interactive=True),
            14, _tracker_rows(),
            15, _serialize_result(result),
            16, _review_guide_html("ready", package_id=result.package.package_id),
        )
    except Exception as exc:  # noqa: BLE001 - never let Gradio swallow a silent failure
        logger.exception("analyze callback crashed")
        yield fail(f"Unexpected error: {exc}")


def _load_package(state) -> ScreeningPrep | None:
    if not state:
        return None
    try:
        return ScreeningPrep.model_validate(state)
    except Exception:  # noqa: BLE001
        return None


def _current_status(package: ScreeningPrep) -> tuple[ReviewStatus, int]:
    stored = _STORE.get_package(package.package_id)
    if stored:
        return ReviewStatus(stored["status"]), int(stored["revision_count"])
    return ReviewStatus.DRAFT, 0


def approve(state, feedback):
    """Returns the shared decision-dock outputs (guide + three buttons + status…)."""
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
            _tracker_rows(),
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
            _tracker_rows(),
            gr.update(),
        )
    return (
        _review_guide_html("approved", package_id=package.package_id),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        f"Approved — prep bundle `{package.package_id}` is ready to use. "
        "Next: open **Interview prep plan**, **Mock interview**, or **Prep coach**.",
        package.model_dump(),
        _package_html(package, []),
        _tracker_rows(),
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
            _tracker_rows(),
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
            _tracker_rows(),
            gr.update(),
        )
    return (
        _review_guide_html("rejected", package_id=package.package_id),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        f"Rejected — prep bundle `{package.package_id}` will not be used.",
        package.model_dump(),
        _package_html(package, []),
        _tracker_rows(),
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
    outputs = list(_empty_outputs())

    def emit(*pairs) -> tuple:
        for position in range(0, len(pairs), 2):
            outputs[pairs[position]] = pairs[position + 1]
        return tuple(outputs)

    package = _load_package(state)

    def fail(message: str) -> tuple:
        return emit(
            0, _alert_html(message, kind="error"),
            1, "Revision could not finish — see the message above.",
            3, _stages_html(-1),
            9, gr.update(interactive=bool(package)),
            10, gr.update(interactive=bool(package)),
            11, gr.update(interactive=bool(package)),
            12, state,
            13, gr.update(interactive=bool(package)),
            16, _review_guide_html(
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
        screening_questions=list(saved.get("screening_questions") or []),
        revision_notes=notes,
    )

    yield emit(
        0, "",
        1, (
            f"**Revision {outcome.revision_count}…** updating your experience from the "
            "notes and re-analyzing the match."
        ),
        3, _stages_html(1, "Merging your experience updates…"),
        9, gr.update(interactive=False),
        10, gr.update(interactive=False),
        11, gr.update(interactive=False),
        12, state,
        13, gr.update(value=notes, interactive=False),
        16, _review_guide_html(
            "working",
            package_id=package.package_id,
            detail="Analyze is running again with your experience updates…",
        ),
    )

    stages: dict[str, object] = {"index": 1, "detail": "Applying your revision notes…"}

    def progress(message: str) -> None:
        lowered = message.lower()
        if "crew output unavailable" in lowered or "direct mcp calls" in lowered:
            stages["index"], stages["detail"] = 7, "Preparing screening answers…"
        elif "six-agent crew" in lowered:
            stages["index"], stages["detail"] = 2, "Re-reading your resume…"
        else:
            stages["detail"] = message

    def on_task(output) -> None:
        name = getattr(output, "name", "") or ""
        agent = getattr(output, "agent", "") or ""
        stage = _AGENT_STAGE.get(agent) or _TASK_STAGE.get(name)
        if stage:
            title = next((t for n, t, _ in STAGES if n == stage), name or agent)
            stages["index"] = stage + 1
            stages["detail"] = f"Finished: {title}"

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run_analysis, request, progress=progress, on_task=on_task)
            expected = 2
            last_yielded = 1
            while not future.done():
                reported = int(stages["index"])
                if reported >= expected:
                    expected = reported + 1
                target = min(expected, _TOTAL_STAGES)
                if target != last_yielded:
                    last_yielded = target
                    detail = str(stages["detail"] or "Working…")
                    yield emit(3, _stages_html(target, detail), 1, detail)
                _wait_futures([future], timeout=1.0)

            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                logger.exception("revision re-run failed")
                yield fail(str(exc) or "Revision re-run failed unexpectedly.")
                return

        _REVIEW.submit_for_review(
            {
                "resume_path": request.resume_path,
                "resume_text": request.resume_text,
                "jd_path": request.jd_path,
                "jd_text": request.jd_text,
                "seniority": request.seniority,
                "screening_questions": request.screening_questions,
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
        yield emit(
            0, "",
            1, status,
            3, _stages_html(_FINAL, "Experience updated — review the new match report."),
            4, _trace_markdown(result),
            5, _insight_html(result),
            6, _prep_html(result.prep_plan),
            7, _package_html(result.package, result.warnings),
            8, result.package.model_dump_json(indent=2),
            9, gr.update(interactive=True),
            10, gr.update(interactive=True),
            11, gr.update(interactive=True),
            12, result.package.model_dump(),
            13, gr.update(value="", interactive=True),
            14, _tracker_rows(),
            15, _serialize_result(result),
            16, _review_guide_html("ready", package_id=result.package.package_id),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("request_revision crashed")
        yield fail(f"Unexpected error: {exc}")


def _read_sample(name: str) -> str:
    try:
        with open(os.path.join(_SAMPLES_DIR, name), encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


_SAMPLE_QUESTIONS = (
    "Are you authorized to work in the United States?\n"
    "What is your notice period?\n"
    "Do you require visa sponsorship?"
)

# --------------------------------------------------------------------------- #
# Interview + coaching callbacks
# --------------------------------------------------------------------------- #
def _turns_to_messages(session: MockInterviewSession) -> list[dict]:
    """Convert the transcript to Gradio chatbot messages (interviewer = assistant)."""
    messages: list[dict] = []
    for turn in session.turns:
        role = "assistant" if turn.role is InterviewTurnRole.INTERVIEWER else "user"
        messages.append({"role": role, "content": turn.text})
    return messages


def _question_html(question: InterviewQuestion | None, *, done: bool = False) -> str:
    if done or question is None:
        return (
            "<div class='cc-card'><h3>Interview complete</h3>"
            "<div class='cc-empty'><strong>You finished the mock interview</strong>"
            "Review your score and the per-question feedback below, then ask the "
            "post-interview coach anything you like.</div></div>"
        )
    return (
        "<div class='cc-card'><h3>Interviewer</h3>"
        "<p class='cc-hint'>Question "
        f"{question.index + 1} of the mock interview</p>"
        f"<p style='font-size:16px;line-height:1.55;color:var(--cc-ink);margin:6px 0'>{_esc(question.text)}</p>"
        "<div class='cc-cite'>"
        "<span class='cc-cite-label'>Looking for</span>"
        "<span class='cc-cite-fact'>"
        f"{_esc(question.intent or question.target_competency or 'a grounded, specific answer')}"
        "</span></div>"
        "</div>"
    )


def _evaluation_html(evaluation: AnswerEvaluation | None) -> str:
    if evaluation is None:
        return ""
    strengths = "".join(f"<li>{_esc(s)}</li>" for s in evaluation.strengths)
    improvements = "".join(f"<li>{_esc(i)}</li>" for i in evaluation.improvements)
    outline = "".join(f"<li>{_esc(o)}</li>" for o in evaluation.model_answer_outline)
    return (
        "<div class='cc-card'><h3>Feedback on your answer</h3>"
        "<div class='cc-stats'>"
        f"<span class='cc-chip'>score · {int(evaluation.score)}/100</span>"
        "</div>"
        "<div class='cc-section-title'>What the interviewer was looking for</div>"
        f"<p style='color:var(--cc-ink-2);font-size:13.5px;line-height:1.55'>{_esc(evaluation.what_interviewer_wanted)}</p>"
        + (f"<div class='cc-section-title'>What worked</div><ul class='cc-list'>{strengths}</ul>" if strengths else "")
        + (f"<div class='cc-section-title'>What to improve</div><div class='cc-note'><ul class='cc-list'>{improvements}</ul></div>" if improvements else "")
        + (f"<div class='cc-section-title'>A stronger answer would</div><ul class='cc-list'>{outline}</ul>" if outline else "")
        + "</div>"
    )


def _overall_html(session: MockInterviewSession) -> str:
    if not session.completed:
        return ""
    return (
        "<div class='cc-card'><h3>Overall performance</h3>"
        "<div class='cc-meter'><div class='cc-meter-top'>"
        f"<div class='cc-score'>{int(session.overall_score)}<small>/100</small></div>"
        "<div class='cc-meter-label'>Average across your answers</div></div>"
        f"<div class='cc-bar'><span style='width:{int(session.overall_score)}%'></span></div></div>"
        f"<p style='color:var(--cc-ink-2);font-size:14px;line-height:1.6'>{_esc(session.overall_summary)}</p>"
        "</div>"
    )


def _audio_status() -> str:
    if audio.audio_available():
        return ""
    return (
        "<div class='cc-alert info'><strong>Text-only practice mode</strong>"
        "Voice is unavailable (no audio-capable API key), so questions are shown as "
        "text and you can type your answers. Add an OpenAI key to enable the voice "
        "interviewer.</div>"
    )


def interview_start(ctx_state, count: int) -> tuple:
    """Begin a mock interview: generate questions and ask the first one."""
    context = _load_context(ctx_state)
    if not context:
        return (
            _alert_html("Analyze a match first — the interview uses your resume and the role."),
            _question_html(None, done=True),
            None,
            [],
            "",
            "",
            None,
        )
    models = _context_models(context)
    questions = interview.generate_questions(
        models["profile"],
        models["requirements"],
        models["gaps"],
        models["prep_plan"],
        int(count or _SETTINGS.interview_question_count),
        llm=llm.callable_or_none(),
    )
    if not questions:
        return (
            _alert_html("No interview questions could be generated. Try analyzing again."),
            _question_html(None, done=True),
            None,
            [],
            "",
            "",
            None,
        )

    session = MockInterviewSession(
        session_id=interview.make_session_id(),
        role_title=(models["requirements"].seniority or "the role"),
        questions=questions,
    )
    return _ask_question(session, 0)


def _ask_question(session: MockInterviewSession, index: int, *, error: str = "") -> tuple:
    """Append the interviewer's question turn, synthesize audio, and render."""
    question = session.questions[index]
    audio_path = audio.speak(question.text) or ""
    question.audio_ref = audio_path
    interview.append_turn(
        session, InterviewTurnRole.INTERVIEWER, question.text, question_index=index
    )
    _STORE.save_interview(session)
    return (
        _alert_html(error) if error else _audio_status(),
        _question_html(question),
        audio_path or None,
        _turns_to_messages(session),
        "",
        "",
        session.model_dump_json(),
    )


def interview_submit(ctx_state, iv_state, answer_text, answer_audio) -> tuple:
    """Evaluate the candidate's answer, then move to the next question."""
    context = _load_context(ctx_state)
    session = _load_interview(iv_state)
    if context is None or session is None:
        return (
            _alert_html("Start the interview first."),
            _question_html(None, done=True),
            None,
            [],
            "",
            "",
            iv_state,
        )

    index = sum(1 for e in session.evaluations)
    if index >= len(session.questions):
        return (
            "",
            _question_html(None, done=True),
            None,
            _turns_to_messages(session),
            "",
            _overall_html(session),
            session.model_dump_json(),
        )

    question = session.questions[index]

    # Prefer the transcript of the recorded audio; fall back to typed text.
    transcript = audio.transcribe(answer_audio) if answer_audio else ""
    answer = transcript.strip() or (answer_text or "").strip()

    problems = guardrails.validate_interview_answer(answer)
    if problems:
        return (
            _alert_html("Please answer the question: " + "; ".join(problems)),
            _question_html(question),
            None,
            _turns_to_messages(session),
            _evaluation_html(session.evaluations[-1] if session.evaluations else None),
            "",
            session.model_dump_json(),
        )

    models = _context_models(context)
    context_bundle = {
        "role": models["requirements"].model_dump(),
        "gaps": models["gaps"].model_dump(),
        "prep_plan": models["prep_plan"].model_dump(),
    }
    evaluation = interview.evaluate_answer(
        question, answer, context_bundle, llm=llm.callable_or_none()
    )
    eval_problems = guardrails.validate_evaluation(evaluation)
    session.evaluations.append(evaluation)
    interview.append_turn(
        session,
        InterviewTurnRole.CANDIDATE,
        answer,
        question_index=index,
        audio_ref=str(answer_audio or ""),
    )

    next_index = index + 1
    if next_index < len(session.questions):
        session.overall_score = round(
            sum(e.score for e in session.evaluations) / len(session.evaluations)
        )
        _STORE.save_interview(session)
        question_out = _ask_question(session, next_index)
        # Splice the evaluation feedback into the returned tuple.
        return (
            question_out[0],
            question_out[1],
            question_out[2],
            question_out[3],
            _evaluation_html(evaluation),
            "",
            question_out[6],
        )

    # Final answer: finish the session and score it.
    score, summary = interview.overall_evaluation(session, llm=llm.callable_or_none())
    session.overall_score = score
    session.overall_summary = summary
    session.completed = True
    _STORE.save_interview(session)
    return (
        _alert_html("; ".join(eval_problems)) if eval_problems else _audio_status(),
        _question_html(None, done=True),
        None,
        _turns_to_messages(session),
        _evaluation_html(evaluation),
        _overall_html(session),
        session.model_dump_json(),
    )


def _load_interview(iv_state) -> MockInterviewSession | None:
    if not iv_state:
        return None
    try:
        return MockInterviewSession.model_validate_json(iv_state)
    except Exception:  # noqa: BLE001
        return None


def _render_prep_chat(history, message: str, ctx_state):
    """Prep coach: resume improvement + preparation chat."""
    history = history or []
    context = _load_context(ctx_state)
    context_text = coach.build_context() if context else "No analysis yet."
    if context:
        models = _context_models(context)
        context_text = coach.build_context(
            profile=models["profile"],
            requirements=models["requirements"],
            gaps=models["gaps"],
            prep_plan=models["prep_plan"],
        )
    prompt = message.get("text", "") if isinstance(message, dict) else str(message)
    reply, warnings = coach.prep_coach_reply(
        prompt, context_text, history, llm=llm.callable_or_none()
    )
    if warnings:
        reply += "\n\n_" + " ".join(warnings) + "_"
    history = history + [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": reply},
    ]
    session_id = _context_models(context)["package_id"] if context else "session"
    _STORE.add_chat_message(session_id, "prep", "user", prompt)
    _STORE.add_chat_message(session_id, "prep", "assistant", reply)
    return history, ""


def _render_post_chat(history, message: str, ctx_state, iv_state):
    """Post-interview coach: everything about JD, resume, and interview results."""
    history = history or []
    context = _load_context(ctx_state)
    session = _load_interview(iv_state) or _STORE.latest_interview()
    if context:
        models = _context_models(context)
        context_text = coach.build_context(
            profile=models["profile"],
            requirements=models["requirements"],
            gaps=models["gaps"],
            prep_plan=models["prep_plan"],
            interview=session,
            include_interview=session is not None,
        )
    else:
        context_text = coach.build_context(interview=session, include_interview=session is not None)
    prompt = message.get("text", "") if isinstance(message, dict) else str(message)
    reply, warnings = coach.post_coach_reply(
        prompt, context_text, history, llm=llm.callable_or_none()
    )
    if warnings:
        reply += "\n\n_" + " ".join(warnings) + "_"
    history = history + [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": reply},
    ]
    session_id = (session.session_id if session else None) or (
        _context_models(context)["package_id"] if context else "session"
    )
    _STORE.add_chat_message(session_id, "post", "user", prompt)
    _STORE.add_chat_message(session_id, "post", "assistant", reply)
    return history, ""


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #
def build_app() -> gr.Blocks:
    with gr.Blocks(title="CareerCrew — Match your resume to the role") as demo:
        state = gr.State(None)
        ctx_state = gr.State(None)
        iv_state = gr.State(None)

        gr.HTML(_topbar())
        gr.HTML(_hero())

        with gr.Tabs(elem_classes=["cc-main-tabs"]):
            # ------------------------------------------------------------------ #
            # Tab 1 — Analyze (inputs, progress, results, HITL decision)
            # ------------------------------------------------------------------ #
            with gr.Tab("1 · Analyze match"):
                gr.HTML(
                    "<div class='cc-panel-head' style='margin-bottom:10px'>"
                    "<h3>Analyze match</h3>"
                    "<p class='cc-hint'>Add your resume and the job posting, run Analyze, "
                    "watch progress here, review the result sub-tabs, then approve or "
                    "add missing experience. Progress and decisions live only in this tab.</p></div>"
                )

                with gr.Row(equal_height=True):
                    with gr.Column(scale=1):
                        with gr.Group(elem_classes=["cc-panel"]):
                            gr.HTML(
                                "<div class='cc-panel-head'><h3>Your resume</h3>"
                                "<p class='cc-hint'>Upload a file or paste the text.</p></div>"
                            )
                            sample_resume_btn = gr.Button("Try a sample resume", size="sm")
                            with gr.Tabs():
                                with gr.Tab("Upload file"):
                                    resume_file = gr.File(
                                        label="PDF, DOCX, or TXT",
                                        file_types=[".pdf", ".docx", ".txt"],
                                        elem_classes=["cc-field"],
                                    )
                                with gr.Tab("Paste text"):
                                    resume_text = gr.Textbox(
                                        label="Resume text",
                                        placeholder="Paste your resume here…",
                                        lines=12,
                                        elem_classes=["cc-field"],
                                        show_label=False,
                                    )

                    with gr.Column(scale=1):
                        with gr.Group(elem_classes=["cc-panel"]):
                            gr.HTML(
                                "<div class='cc-panel-head'><h3>The job</h3>"
                                "<p class='cc-hint'>Upload the posting or paste the text. "
                                "URLs are not read directly.</p></div>"
                            )
                            sample_jd_btn = gr.Button("Try a sample job", size="sm")
                            with gr.Tabs():
                                with gr.Tab("Upload file"):
                                    jd_file = gr.File(
                                        label="PDF, DOCX, or TXT",
                                        file_types=[".pdf", ".docx", ".txt"],
                                        elem_classes=["cc-field"],
                                    )
                                with gr.Tab("Paste posting"):
                                    jd_text = gr.Textbox(
                                        label="Job description",
                                        placeholder="Paste the job description here…",
                                        lines=10,
                                        elem_classes=["cc-field"],
                                        show_label=False,
                                    )
                            with gr.Accordion("Optional screening questions", open=False):
                                screening_text = gr.Textbox(
                                    label="One question per line",
                                    placeholder=(
                                        "Are you authorized to work in the US?\n"
                                        "What is your notice period?"
                                    ),
                                    lines=3,
                                    elem_classes=["cc-field"],
                                    show_label=False,
                                )

                with gr.Row(elem_classes=["cc-cta"], equal_height=True):
                    gr.HTML(
                        "<div class='cc-cta-copy'><h3>Ready when you are</h3>"
                        "<p>We’ll score the match, plan interview prep, suggest stronger "
                        "bullets, and prepare honest screening answers.</p></div>",
                        elem_classes=["cc-cta-copy-wrap"],
                    )
                    with gr.Row(elem_classes=["cc-cta-actions"]):
                        run_btn = gr.Button(
                            "Analyze match",
                            variant="primary",
                            elem_classes=["cc-run"],
                            scale=0,
                            min_width=168,
                        )
                        clear_btn = gr.Button(
                            "Clear", elem_classes=["cc-clear"], scale=0, min_width=88
                        )

                error_box = gr.HTML("", elem_classes=["cc-alert-slot"])
                status = gr.Markdown(_IDLE_STATUS, elem_classes=["cc-status-line"])
                banner = gr.HTML(_mode_banner())
                stages_html = gr.HTML(_stages_html(-1))

                with gr.Tabs(elem_classes=["cc-result-tabs"]):
                    with gr.Tab("Match report"):
                        insight_html = gr.HTML(_insight_html(None))
                    with gr.Tab("Interview prep plan"):
                        prep_html = gr.HTML(_prep_html(None))
                    with gr.Tab("Screening answers"):
                        package_md = gr.HTML(_package_html(None))

                with gr.Group(elem_classes=["cc-review"]):
                    review_guide_html = gr.HTML(_review_guide_html("idle"))

                    with gr.Group(elem_classes=["cc-review-choice", "cc-review-choice-a"]):
                        gr.HTML(
                            "<div class='cc-choice-label'>"
                            "<span class='cc-choice-n'>A</span>"
                            "<div><strong>Approve</strong> — the prep bundle looks right. "
                            "Nothing is sent to an employer; this only finalizes it here.</div></div>"
                        )
                        approve_btn = gr.Button(
                            "Approve prep bundle",
                            variant="primary",
                            interactive=False,
                            elem_classes=["cc-approve"],
                        )

                    with gr.Group(elem_classes=["cc-review-choice", "cc-review-choice-b"]):
                        gr.HTML(
                            "<div class='cc-choice-label'>"
                            "<span class='cc-choice-n'>B</span>"
                            "<div><strong>Add missing experience</strong> — e.g. the JD wants "
                            "React but your resume doesn’t list it. Type the update, then press "
                            "the button. <em>Analyze runs again automatically</em> and refreshes "
                            "Match / Prep / Screening.</div></div>"
                        )
                        feedback = gr.Textbox(
                            label="Your experience update",
                            placeholder=(
                                "e.g. I have 5+ years of React experience building production SPAs."
                            ),
                            lines=3,
                            interactive=False,
                            elem_classes=["cc-field"],
                        )
                        revise_btn = gr.Button(
                            "Apply updates & re-analyze",
                            interactive=False,
                            elem_classes=["cc-revise"],
                        )

                    with gr.Group(elem_classes=["cc-review-choice", "cc-review-choice-c"]):
                        gr.HTML(
                            "<div class='cc-choice-label'>"
                            "<span class='cc-choice-n'>C</span>"
                            "<div><strong>Reject</strong> — discard this prep bundle "
                            "(or refresh History).</div></div>"
                        )
                        with gr.Row(elem_classes=["cc-review-actions"]):
                            reject_btn = gr.Button(
                                "Reject prep bundle",
                                interactive=False,
                                elem_classes=["cc-reject"],
                            )
                            refresh_btn = gr.Button(
                                "Refresh history",
                                size="sm",
                                elem_classes=["cc-refresh"],
                            )

                    review_status = gr.Markdown("", elem_classes=["cc-review-status"])

            # ------------------------------------------------------------------ #
            # Tab 2 — Mock interview
            # ------------------------------------------------------------------ #
            with gr.Tab("2 · Mock interview"):
                gr.HTML(
                    "<div class='cc-panel-head'><h3>Voice mock interview</h3>"
                    "<p class='cc-hint'>Requires a finished Analyze first. The interviewer asks "
                    "questions from your resume and the role. Answer by voice or type. "
                    "Practice only — nothing is submitted.</p></div>"
                )
                with gr.Row():
                    iv_start_btn = gr.Button(
                        "Start interview",
                        variant="primary",
                        elem_classes=["cc-run"],
                        scale=0,
                        min_width=168,
                    )
                    iv_questions = gr.Slider(
                        minimum=3,
                        maximum=10,
                        value=_SETTINGS.interview_question_count,
                        step=1,
                        label="Number of questions",
                        scale=1,
                    )
                iv_error = gr.HTML("")
                iv_question_html = gr.HTML(_question_html(None, done=True))
                iv_audio = gr.Audio(
                    label="Interviewer (listen)",
                    autoplay=True,
                    interactive=False,
                    elem_id="cc-iv-audio",
                )
                with gr.Row(equal_height=True):
                    with gr.Column(scale=1):
                        gr.HTML("<div class='cc-section-title'>Your answer</div>")
                        iv_answer_audio = gr.Audio(
                            sources=["microphone"],
                            type="filepath",
                            label="Record your answer",
                        )
                        iv_answer_text = gr.Textbox(
                            label="Or type your answer",
                            placeholder="Type your answer if you prefer not to record…",
                            lines=4,
                            elem_classes=["cc-field"],
                        )
                        iv_submit_btn = gr.Button(
                            "Submit answer",
                            variant="primary",
                            elem_classes=["cc-run"],
                            scale=0,
                            min_width=168,
                        )
                    with gr.Column(scale=1):
                        gr.HTML("<div class='cc-section-title'>Live transcript</div>")
                        iv_chatbot = gr.Chatbot(
                            label="Interview transcript",
                            height=360,
                            elem_id="cc-iv-transcript",
                        )
                iv_feedback_html = gr.HTML("")
                iv_overall_html = gr.HTML("")

            # ------------------------------------------------------------------ #
            # Tab 3 — Prep coach
            # ------------------------------------------------------------------ #
            with gr.Tab("3 · Prep coach"):
                gr.HTML(
                    "<div class='cc-panel-head'><h3>Resume &amp; preparation coach</h3>"
                    "<p class='cc-hint'>Ask anything about improving your resume or preparing "
                    "for this role. Uses your Analyze context when available.</p></div>"
                )
                prep_chat = gr.Chatbot(label="Prep coach", height=380)
                prep_msg = gr.Textbox(
                    label="Your question",
                    placeholder="How should I talk about the AWS gap?",
                    lines=2,
                    elem_classes=["cc-field"],
                )

            # ------------------------------------------------------------------ #
            # Tab 4 — Post-interview coach
            # ------------------------------------------------------------------ #
            with gr.Tab("4 · Post-interview coach"):
                gr.HTML(
                    "<div class='cc-panel-head'><h3>Post-interview coach</h3>"
                    "<p class='cc-hint'>After your mock interview, ask about performance. "
                    "Remembers resume, JD, gaps, prep plan, and interview transcript.</p></div>"
                )
                post_chat = gr.Chatbot(label="Post-interview coach", height=380)
                post_msg = gr.Textbox(
                    label="Your question",
                    placeholder="What should I improve before the real interview?",
                    lines=2,
                    elem_classes=["cc-field"],
                )

            # ------------------------------------------------------------------ #
            # Tab 5 — History
            # ------------------------------------------------------------------ #
            with gr.Tab("5 · History"):
                tracker_table = gr.Dataframe(
                    headers=["Prep bundle", "Role", "Company", "Status", "Revisions", "Updated"],
                    datatype=["str"] * 6,
                    interactive=False,
                    label="Your recent prep bundles",
                    value=_tracker_rows(),
                )

            # ------------------------------------------------------------------ #
            # Advanced
            # ------------------------------------------------------------------ #
            with gr.Tab("Advanced"):
                with gr.Accordion("Step-by-step log", open=True):
                    trace_md = gr.Markdown(_trace_markdown(None))
                with gr.Accordion("Raw screening answers JSON", open=False):
                    package_json = gr.Code(label="Screening answers JSON", language="json")

        gr.HTML(
            "<p class='cc-foot'>CareerCrew keeps everything honest — verified facts only, "
            "practice interviews that never submit anything, and anything uncertain left "
            "for you to answer.</p>"
        )

        # --- wiring --------------------------------------------------------- #
        analyze_outputs = [
            error_box,          # 0
            status,             # 1
            banner,             # 2
            stages_html,        # 3
            trace_md,           # 4
            insight_html,       # 5
            prep_html,          # 6
            package_md,         # 7
            package_json,       # 8
            approve_btn,        # 9
            reject_btn,         # 10
            revise_btn,         # 11
            state,              # 12
            feedback,           # 13
            tracker_table,      # 14
            ctx_state,          # 15
            review_guide_html,  # 16
        ]

        decision_outputs = [
            review_guide_html,
            approve_btn,
            reject_btn,
            revise_btn,
            review_status,
            state,
            package_md,
            tracker_table,
            feedback,
        ]

        run_btn.click(
            analyze,
            inputs=[resume_file, resume_text, jd_file, jd_text, screening_text],
            outputs=analyze_outputs,
        )

        clear_btn.click(
            lambda: (
                gr.update(value=None),
                gr.update(value=""),
                gr.update(value=None),
                gr.update(value=""),
                gr.update(value=""),
                *_empty_outputs(),
            ),
            outputs=[
                resume_file, resume_text, jd_file, jd_text, screening_text,
                *analyze_outputs,
            ],
        )

        sample_resume_btn.click(
            lambda: (gr.update(value=None), gr.update(value=_read_sample("sample_resume.txt"))),
            outputs=[resume_file, resume_text],
        )
        sample_jd_btn.click(
            lambda: (
                gr.update(value=None),
                gr.update(value=_read_sample("sample_jd.txt")),
                gr.update(value=_SAMPLE_QUESTIONS),
            ),
            outputs=[jd_file, jd_text, screening_text],
        )

        # --- mock interview wiring ------------------------------------------ #
        iv_start_btn.click(
            interview_start,
            inputs=[ctx_state, iv_questions],
            outputs=[
                iv_error, iv_question_html, iv_audio, iv_chatbot,
                iv_feedback_html, iv_overall_html, iv_state,
            ],
        )
        iv_submit_btn.click(
            interview_submit,
            inputs=[ctx_state, iv_state, iv_answer_text, iv_answer_audio],
            outputs=[
                iv_error, iv_question_html, iv_audio, iv_chatbot,
                iv_feedback_html, iv_overall_html, iv_state,
            ],
        )

        # --- coaching chat wiring ------------------------------------------- #
        prep_msg.submit(
            _render_prep_chat,
            inputs=[prep_chat, prep_msg, ctx_state],
            outputs=[prep_chat, prep_msg],
        )
        post_msg.submit(
            _render_post_chat,
            inputs=[post_chat, post_msg, ctx_state, iv_state],
            outputs=[post_chat, post_msg],
        )

        approve_btn.click(
            approve,
            inputs=[state, feedback],
            outputs=decision_outputs,
        )
        reject_btn.click(
            reject,
            inputs=[state, feedback],
            outputs=decision_outputs,
        )
        revise_btn.click(
            request_revision,
            inputs=[state, feedback],
            outputs=analyze_outputs,
        )
        refresh_btn.click(_tracker_rows, outputs=[tracker_table])

    return demo


def theme() -> gr.themes.Base:
    """The CareerCrew visual theme (indigo accent, larger radii, Inter font)."""
    return gr.themes.Soft(
        primary_hue=gr.themes.colors.indigo,
        secondary_hue=gr.themes.colors.violet,
        neutral_hue=gr.themes.colors.slate,
        radius_size=gr.themes.sizes.radius_lg,
        font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
    )


def main() -> None:
    """Launch the Gradio app bound to 0.0.0.0 for container deployment."""
    app = build_app()
    app.queue().launch(
        server_name="0.0.0.0",
        server_port=_SETTINGS.app_port,
        show_error=True,
        theme=theme(),
        css=CUSTOM_CSS,
    )


if __name__ == "__main__":
    main()
