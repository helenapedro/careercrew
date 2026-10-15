"""CareerCrew - candidate-facing Gradio product UI.

Plain-language workflow for job seekers:

1. Add a resume (upload or paste) and a job description (paste or URL).
2. Optionally add employer screening questions.
3. Press **Analyze match** and watch live progress.
4. Review coverage, rewrite suggestions, and an honest application package.
5. Approve, request changes, or reject — nothing is finalized without you.

Technical details (agents, MCP, JSON, traces) live under **Advanced**.
Screening answers come only from a verified answer bank; unverified questions
are surfaced for the candidate instead of being invented.
"""

from __future__ import annotations

import html
import logging
import os
import shutil
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, wait as _wait_futures

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
    (6, "Screening answers", "Fill employer questions only from verified answers"),
    (7, "Final check", "Verify honesty rules, then hand the draft to you"),
]
_TOTAL_STAGES = len(STAGES)
_FINAL = _TOTAL_STAGES + 1  # sentinel: marks every stage complete

#: Map CrewAI agent names to the stage they belong to, for live progress.
_AGENT_STAGE = {
    "Profile Extractor": 2,
    "JD Analyzer": 3,
    "Gap Analyst": 4,
    "Feedback Writer": 5,
    "Application Packager": 6,
}
_TASK_STAGE = {
    "extract_profile": 2,
    "analyze_jd": 3,
    "analyze_gaps": 4,
    "write_feedback": 5,
    "assemble_package": 6,
}

CUSTOM_CSS = """
:root {
  --cc-bg: #f4f6fb;
  --cc-surface: #ffffff;
  --cc-surface-2: #f8fafc;
  --cc-line: #e5e9f2;
  --cc-ink: #0f172a;
  --cc-ink-2: #334155;
  --cc-muted: #64748b;
  --cc-soft: #f1f5f9;
  --cc-accent: #4f46e5;
  --cc-accent-2: #6366f1;
  --cc-ok: #16a34a;
  --cc-warn: #d97706;
  --cc-bad: #dc2626;
  --cc-shadow: rgba(15, 23, 42, .18);
}
body.dark {
  --cc-bg: #0b1220;
  --cc-surface: #121a2b;
  --cc-surface-2: #172033;
  --cc-line: #273449;
  --cc-ink: #f1f5f9;
  --cc-ink-2: #cbd5e1;
  --cc-muted: #94a3b8;
  --cc-soft: #1e293b;
  --cc-accent: #818cf8;
  --cc-accent-2: #a5b4fc;
  --cc-ok: #4ade80;
  --cc-warn: #fbbf24;
  --cc-bad: #f87171;
  --cc-shadow: rgba(0, 0, 0, .45);
}

.gradio-container {
  max-width: 1180px !important;
  margin: 0 auto !important;
  padding-top: 18px !important;
  background:
    radial-gradient(900px 380px at 12% -8%, color-mix(in srgb, var(--cc-accent) 14%, transparent), transparent 58%),
    radial-gradient(700px 320px at 92% 0%, color-mix(in srgb, #06b6d4 10%, transparent), transparent 52%),
    var(--cc-bg) !important;
  color: var(--cc-ink) !important;
}
footer { display: none !important; }
.contain { gap: 14px !important; }

[data-testid="block-info"] {
  background: transparent !important; border: none !important;
  color: var(--cc-muted) !important; font-size: 12px !important;
  font-weight: 600 !important; padding: 0 !important; margin-bottom: 6px !important;
}

/* ---- brand bar ---- */
.cc-topbar {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 10px 4px 4px 4px;
}
.cc-brand { display: flex; align-items: center; gap: 10px; }
.cc-mark {
  width: 34px; height: 34px; border-radius: 10px;
  background: linear-gradient(135deg, var(--cc-accent), #06b6d4);
  color: #fff; display: grid; place-items: center; font-weight: 800; font-size: 14px;
  box-shadow: 0 10px 22px -14px var(--cc-accent);
}
.cc-brand-name { font-size: 18px; font-weight: 760; letter-spacing: -0.02em; color: var(--cc-ink); }
.cc-brand-tag { font-size: 12px; color: var(--cc-muted); margin-top: 1px; }
.cc-status-chip {
  display: inline-flex; align-items: center; gap: 7px;
  padding: 7px 12px; border-radius: 999px; font-size: 12px; font-weight: 650;
  border: 1px solid var(--cc-line); background: var(--cc-surface); color: var(--cc-ink-2);
}
.cc-status-chip .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--cc-ok); }
.cc-status-chip.warn .dot { background: var(--cc-warn); }

.cc-hero {
  border: 1px solid var(--cc-line); border-radius: 22px; padding: 28px 28px 24px;
  background:
    linear-gradient(145deg, color-mix(in srgb, var(--cc-accent) 12%, transparent), transparent 55%),
    var(--cc-surface);
  box-shadow: 0 24px 48px -36px var(--cc-shadow);
}
.cc-hero h1 {
  margin: 0 0 8px 0; font-size: clamp(28px, 4vw, 40px); line-height: 1.12;
  letter-spacing: -0.03em; font-weight: 780; color: var(--cc-ink); max-width: 18ch;
}
.cc-hero .cc-sub {
  margin: 0 0 16px 0; color: var(--cc-ink-2); font-size: 15.5px; line-height: 1.55; max-width: 54ch;
}
.cc-trust { display: flex; flex-wrap: wrap; gap: 8px; }
.cc-trust span {
  font-size: 12px; font-weight: 650; color: var(--cc-ink-2);
  background: var(--cc-soft); border: 1px solid var(--cc-line);
  padding: 6px 11px; border-radius: 999px;
}

.cc-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 650;
  border: 1px solid transparent;
}
.cc-badge.on  { background: color-mix(in srgb, var(--cc-ok) 14%, transparent); color: var(--cc-ok); border-color: color-mix(in srgb, var(--cc-ok) 34%, transparent); }
.cc-badge.off { background: color-mix(in srgb, var(--cc-warn) 14%, transparent); color: var(--cc-warn); border-color: color-mix(in srgb, var(--cc-warn) 34%, transparent); }
.cc-badge.ghost { background: var(--cc-soft); color: var(--cc-ink-2); border-color: var(--cc-line); }
.cc-badge.covered { background: color-mix(in srgb, var(--cc-ok) 16%, transparent); color: var(--cc-ok); border-color: color-mix(in srgb, var(--cc-ok) 38%, transparent); }
.cc-badge.reframeable { background: color-mix(in srgb, var(--cc-warn) 16%, transparent); color: var(--cc-warn); border-color: color-mix(in srgb, var(--cc-warn) 38%, transparent); }
.cc-badge.out { background: color-mix(in srgb, var(--cc-bad) 16%, transparent); color: var(--cc-bad); border-color: color-mix(in srgb, var(--cc-bad) 38%, transparent); }
.cc-badge.src { background: var(--cc-soft); color: var(--cc-ink-2); border-color: var(--cc-line); font-family: ui-monospace, monospace; }

.cc-card {
  border: 1px solid var(--cc-line); border-radius: 18px; background: var(--cc-surface);
  padding: 18px 20px; box-shadow: 0 16px 34px -30px var(--cc-shadow);
}
.cc-card h3 { margin: 0 0 4px 0; font-size: 16px; font-weight: 720; color: var(--cc-ink); letter-spacing: -0.01em; }
.cc-card .cc-hint { color: var(--cc-muted); font-size: 13px; margin: 0 0 14px 0; line-height: 1.5; }
.cc-empty {
  border: 1px dashed color-mix(in srgb, var(--cc-line) 90%, transparent);
  border-radius: 14px; padding: 28px 22px; text-align: center;
  color: var(--cc-muted); background: var(--cc-surface-2); font-size: 13.5px; line-height: 1.55;
}
.cc-empty strong { display: block; color: var(--cc-ink); font-size: 14.5px; margin-bottom: 4px; }

/* ---- input panels ---- */
.cc-panel {
  border: 1px solid var(--cc-line) !important; border-radius: 20px !important;
  background: var(--cc-surface) !important; padding: 8px 12px 14px !important;
  box-shadow: 0 16px 34px -30px var(--cc-shadow); min-height: 100%;
}
.cc-panel-head { margin: 6px 2px 12px; }
.cc-panel-head h3 { margin: 0; font-size: 17px; font-weight: 740; color: var(--cc-ink); letter-spacing: -0.015em; }
.cc-panel-head .cc-hint { margin: 4px 0 0; color: var(--cc-muted); font-size: 13px; }
.cc-field textarea, .cc-field input[type="text"], .cc-field input[type="url"] {
  background: var(--cc-soft) !important; color: var(--cc-ink) !important;
  border: 1px solid var(--cc-line) !important; border-radius: 12px !important;
}
.cc-field textarea::placeholder, .cc-field input::placeholder { color: var(--cc-muted) !important; opacity: .9; }
.cc-cta {
  border: 1px solid var(--cc-line); border-radius: 18px; background: var(--cc-surface);
  padding: 14px 16px; box-shadow: 0 16px 34px -30px var(--cc-shadow);
}
.cc-cta-row { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; }
.cc-cta-copy h3 { margin: 0; font-size: 15px; font-weight: 700; color: var(--cc-ink); }
.cc-cta-copy p { margin: 3px 0 0; font-size: 12.5px; color: var(--cc-muted); }

button.cc-run {
  background: linear-gradient(135deg, var(--cc-accent), var(--cc-accent-2)) !important;
  border: none !important; color: #fff !important; font-weight: 720 !important;
  box-shadow: 0 14px 28px -16px color-mix(in srgb, var(--cc-accent) 80%, transparent) !important;
  min-height: 46px; min-width: 180px; border-radius: 12px !important;
}

/* ---- horizontal progress stepper ---- */
.cc-progress { margin-top: 4px; }
.cc-progress-top {
  display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px;
}
.cc-progress-top .cc-progress-label { font-size: 13px; color: var(--cc-muted); }
.cc-progress-top .cc-progress-count { font-size: 13px; font-weight: 700; color: var(--cc-ink); }
.cc-stages {
  display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 0;
  position: relative;
}
@media (max-width: 980px) {
  .cc-stages { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
}
@media (max-width: 640px) {
  .cc-stages { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
}
.cc-stage {
  position: relative; padding: 0 8px; text-align: center;
}
.cc-stage::before {
  content: ""; position: absolute; top: 15px; left: 0; right: 0; height: 2px;
  background: var(--cc-line); z-index: 0;
}
.cc-stage:first-child::before { left: 50%; }
.cc-stage:last-child::before { right: 50%; }
.cc-stage .cc-dot {
  position: relative; z-index: 1; margin: 0 auto 8px;
  width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center;
  font-size: 12px; font-weight: 750; background: var(--cc-soft); color: var(--cc-muted);
  border: 2px solid var(--cc-line);
}
.cc-stage .cc-ttl { font-weight: 680; font-size: 12.5px; color: var(--cc-ink); line-height: 1.25; }
.cc-stage .cc-blurb { display: none; }
.cc-stage .cc-pill {
  margin-top: 6px; display: inline-block;
  font-size: 10px; font-weight: 750; letter-spacing: .05em;
  padding: 3px 8px; border-radius: 999px; background: var(--cc-soft); color: var(--cc-muted);
}
.cc-stage.done .cc-dot { background: color-mix(in srgb, var(--cc-ok) 18%, transparent); color: var(--cc-ok); border-color: var(--cc-ok); }
.cc-stage.done .cc-pill { background: color-mix(in srgb, var(--cc-ok) 16%, transparent); color: var(--cc-ok); }
.cc-stage.done::before { background: color-mix(in srgb, var(--cc-ok) 55%, var(--cc-line)); }
.cc-stage.active .cc-dot {
  background: color-mix(in srgb, var(--cc-accent) 18%, transparent); color: var(--cc-accent);
  border-color: var(--cc-accent); animation: cc-pulse 1.2s infinite;
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--cc-accent) 16%, transparent);
}
.cc-stage.active .cc-pill { background: color-mix(in srgb, var(--cc-accent) 16%, transparent); color: var(--cc-accent); }
.cc-stage.active .cc-ttl { color: var(--cc-accent); }
@keyframes cc-pulse { 0%,100% { opacity: 1 } 50% { opacity: .55 } }
.cc-live {
  margin-top: 14px; border-radius: 12px; padding: 11px 13px;
  background: var(--cc-soft); border: 1px solid var(--cc-line);
  color: var(--cc-ink-2); font-size: 13px;
  display: flex; align-items: center; gap: 8px;
}
.cc-live .cc-blink { color: var(--cc-accent); animation: cc-pulse 1.1s infinite; font-weight: 700; }

/* ---- results ---- */
.cc-meter { margin: 4px 0 18px; }
.cc-meter .cc-meter-top { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.cc-meter .cc-score { font-size: 34px; font-weight: 800; letter-spacing: -0.03em; color: var(--cc-ink); }
.cc-meter .cc-score small { font-size: 14px; color: var(--cc-muted); font-weight: 600; }
.cc-meter .cc-meter-label { font-size: 12px; color: var(--cc-muted); font-weight: 650; text-align: right; }
.cc-bar { height: 10px; border-radius: 999px; background: var(--cc-soft); overflow: hidden; }
.cc-bar > span {
  display: block; height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, var(--cc-accent), #06b6d4);
}
.cc-stats { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.cc-chip {
  font-size: 12px; font-weight: 650; padding: 5px 10px; border-radius: 999px;
  background: var(--cc-soft); color: var(--cc-ink-2); border: 1px solid var(--cc-line);
}
.cc-chip.covered { background: color-mix(in srgb, var(--cc-ok) 16%, transparent); color: var(--cc-ok); border-color: color-mix(in srgb, var(--cc-ok) 38%, transparent); }
.cc-chip.reframeable { background: color-mix(in srgb, var(--cc-warn) 16%, transparent); color: var(--cc-warn); border-color: color-mix(in srgb, var(--cc-warn) 38%, transparent); }
.cc-chip.out { background: color-mix(in srgb, var(--cc-bad) 16%, transparent); color: var(--cc-bad); border-color: color-mix(in srgb, var(--cc-bad) 38%, transparent); }
.cc-section-title {
  font-size: 12px; font-weight: 750; text-transform: uppercase; letter-spacing: .08em;
  color: var(--cc-muted); margin: 22px 0 10px;
}
.cc-table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
.cc-table th {
  text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
  color: var(--cc-muted); padding: 8px 10px; border-bottom: 1px solid var(--cc-line);
}
.cc-table td { padding: 11px 10px; border-bottom: 1px solid var(--cc-line); vertical-align: top; color: var(--cc-ink-2); }
.cc-bullets { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; }
.cc-bullets li { border: 1px solid var(--cc-line); border-radius: 14px; padding: 13px 14px; background: var(--cc-surface-2); }
.cc-bullets li p { margin: 0 0 7px; color: var(--cc-ink); font-size: 14px; line-height: 1.55; }
.cc-cite { font-size: 12px; color: var(--cc-muted); }
.cc-cite b { color: var(--cc-accent); }
.cc-list { margin: 0; padding-left: 18px; color: var(--cc-ink-2); font-size: 13.5px; line-height: 1.65; }
.cc-note {
  border: 1px solid color-mix(in srgb, var(--cc-warn) 38%, transparent);
  background: color-mix(in srgb, var(--cc-warn) 12%, transparent); color: var(--cc-warn);
  border-radius: 12px; padding: 11px 13px; font-size: 13px; margin-top: 10px;
}
.cc-note .cc-list { color: var(--cc-ink-2); }
.cc-qa { display: flex; flex-direction: column; gap: 10px; }
.cc-qa-item {
  border: 1px solid var(--cc-line); border-radius: 14px; padding: 14px 15px; background: var(--cc-surface-2);
}
.cc-qa-item .cc-q { margin: 0 0 6px; font-weight: 680; color: var(--cc-ink); font-size: 13.5px; }
.cc-qa-item .cc-a { margin: 0 0 8px; color: var(--cc-ink-2); font-size: 13.5px; line-height: 1.55; }
.cc-review {
  border: 1px solid var(--cc-line); border-radius: 18px; background: var(--cc-surface);
  padding: 16px 18px; box-shadow: 0 16px 34px -30px var(--cc-shadow);
}
.cc-foot { color: var(--cc-muted); font-size: 12px; margin: 8px 0 18px; text-align: center; }
"""


# --------------------------------------------------------------------------- #
# Small rendering helpers
# --------------------------------------------------------------------------- #
def _esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""))


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
        "<p class='cc-sub'>See what you already cover, what you can reframe, and what to leave out. "
        "Get stronger resume bullets and honest screening answers — all grounded in your real experience.</p>"
        "<div class='cc-trust'>"
        "<span>Cited from your resume</span>"
        "<span>No invented answers</span>"
        "<span>You approve before finalize</span>"
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
        "<div><h3 style='margin:0'>Progress</h3>"
        "<div class='cc-progress-label'>We’ll walk through each step as your match is prepared.</div></div>"
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
        parts.append("<div class='cc-section-title'>Suggested resume rewrites</div>")
        bullets = "".join(
            "<li>"
            f"<p>{_esc(bullet.text)}</p>"
            f"<div class='cc-cite'>Based on: <b>{_esc(bullet.cited_fact) or '—'}</b></div>"
            "</li>"
            for bullet in feedback.rewritten_bullets
        )
        parts.append(f"<ul class='cc-bullets'>{bullets}</ul>")

    if feedback.talking_points:
        parts.append("<div class='cc-section-title'>Interview talking points</div>")
        items = "".join(f"<li>{_esc(point)}</li>" for point in feedback.talking_points)
        parts.append(f"<ul class='cc-list'>{items}</ul>")

    if feedback.do_not_claim:
        items = "".join(f"<li>{_esc(item)}</li>" for item in feedback.do_not_claim)
        parts.append(
            "<div class='cc-section-title'>Do not claim</div>"
            f"<div class='cc-note'><ul class='cc-list'>{items}</ul></div>"
        )

    parts.append("</div>")
    return "".join(parts)


def _package_html(package: ApplicationPackage | None, warnings: list[str] | None = None) -> str:
    """Candidate-facing application package (screening answers + items needing input)."""
    if package is None:
        return _empty_card(
            "Application package",
            "After analysis, you’ll see verified screening answers here — and anything that "
            "still needs your personal input.",
        )

    parts = ["<div class='cc-card'>"]
    parts.append("<h3>Application package</h3>")
    role = package.role_title or "Role"
    company = package.company or "Company"
    parts.append(
        f"<p class='cc-hint'><span class='cc-badge ghost'>{_esc(package.package_id)}</span> "
        f"{_esc(role)} · {_esc(company)}</p>"
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
        items = "".join(f"<li>{_esc(item)}</li>" for item in package.do_not_claim)
        parts.append(
            f"<div class='cc-section-title'>Needs your input ({len(package.do_not_claim)})</div>"
            "<div class='cc-note'><p style='margin:0 0 6px'>We won’t invent answers for these. "
            f"Please fill them in yourself.</p><ul class='cc-list'>{items}</ul></div>"
        )

    if warnings:
        notes = "".join(f"<li>{_esc(w)}</li>" for w in warnings)
        parts.append(
            f"<div class='cc-section-title'>Notes</div><ul class='cc-list'>{notes}</ul>"
        )

    parts.append("</div>")
    return "".join(parts)


def _package_markdown(package: ApplicationPackage | None, warnings: list[str] | None = None) -> str:
    """Plain markdown fallback used by review callbacks / tests that inspect text."""
    if package is None:
        return "Application package will appear here after analysis. Answers use answer_bank only."
    lines = [
        f"### {package.package_id}",
        f"**{package.role_title or '—'}** at **{package.company or '—'}**",
        "",
    ]
    if package.package_summary:
        lines += [package.package_summary, ""]
    lines.append(f"#### Screening answers ({len(package.screening_answers)})")
    for index, answer in enumerate(package.screening_answers, start=1):
        lines.append(
            f"**Q{index}. {answer.question}**  \n{answer.answer}  \n"
            f"`source: {answer.source}` · verified: {'yes' if answer.verified else 'no'}"
        )
        lines.append("")
    if package.do_not_claim:
        lines.append(f"#### Needs your input ({len(package.do_not_claim)})")
        lines.extend(f"- {item}" for item in package.do_not_claim)
    if warnings:
        lines.append("#### Notes")
        lines.extend(f"- {warning}" for warning in warnings)
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


def _empty_outputs() -> tuple:
    """The reset state shared by every early return in :func:`analyze`."""
    return (
        gr.update(value="", visible=False),  # error_box
        _IDLE_STATUS,  # status
        _mode_banner(),  # banner
        _stages_html(-1),  # stages_html
        _trace_markdown(None),  # trace_md
        _insight_html(None),  # insight_html
        _package_html(None),  # package_md (HTML package view)
        "",  # package_json
        gr.update(interactive=False),  # approve_btn
        gr.update(interactive=False),  # reject_btn
        gr.update(interactive=False),  # revise_btn
        None,  # state
        "",  # review_feedback
        _tracker_rows(),  # tracker_table
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
            destination = os.path.abspath(os.path.join(base, os.path.basename(check_name)))
            if not destination.startswith(base + os.sep):
                raise ValueError("invalid resume path")
            shutil.copyfile(check_name, destination)
            return os.path.basename(destination), None
    if (resume_text or "").strip():
        return None, guardrails.redact_pii(resume_text)
    return None, None


def analyze(resume_file, resume_text, jd_text, jd_url, screening_text) -> Iterator[tuple]:
    """Generator callback: streams live stage progress, then the final results."""
    outputs = list(_empty_outputs())

    def emit(*pairs) -> tuple:
        """Build the full output tuple from ``index, value`` pairs."""
        current = list(outputs)
        for position in range(0, len(pairs), 2):
            current[pairs[position]] = pairs[position + 1]
        return tuple(current)

    jd_source = (jd_url or "").strip() or (jd_text or "").strip()

    # --- Stage 1: input guardrails (resume resolution). --------------------- #
    try:
        resume_path, pasted = _resolve_resume(resume_file, resume_text)
    except Exception as exc:  # noqa: BLE001 - surface a clean error
        yield emit(
            0, gr.update(value=f"**Resume error** — {exc}", visible=True),
            1, "Resume rejected — see the message above.",
        )
        return

    if resume_path is None and pasted is None:
        yield emit(
            0, gr.update(value="Provide a resume: upload a PDF/DOCX/TXT file, or paste the text.", visible=True),
            1, "Missing resume.",
        )
        return

    if not jd_source.strip():
        yield emit(
            0, gr.update(value="Paste a job description or an https URL.", visible=True),
            1, "Missing job description.",
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

    # Kick off: stage 1 is active.
    yield emit(
        0, gr.update(value="", visible=False),
        1, "Checking your inputs…",
        3, _stages_html(1, "Checking that your resume and job description look valid"),
    )

    stages: dict[str, object] = {"index": 1, "detail": "Checking your inputs…"}

    def progress(message: str) -> None:
        """Bridge the pipeline's progress messages onto the stage tracker."""
        lowered = message.lower()
        if "crew output unavailable" in lowered or "direct mcp calls" in lowered:
            stages["index"], stages["detail"] = 6, "Preparing screening answers from your verified bank…"
        elif "five-agent crew" in lowered:
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
            yield emit(
                0, gr.update(value=f"**Analysis failed** — {exc}", visible=True),
                1, "Analysis failed — see the message above.",
                3, _stages_html(-1),
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

    mode = " (limited mode)" if result.used_fallback else ""
    status = (
        f"**Your draft is ready{mode}.** "
        f"Package `{result.package.package_id}` · "
        f"{len(result.package.screening_answers)} verified screening answer(s) · "
        f"{len(result.package.do_not_claim)} item(s) still need your input."
    )
    yield emit(
        0, gr.update(value="", visible=False),
        1, status,
        3, _stages_html(_FINAL, "All set — review your match report below."),
        4, _trace_markdown(result),
        5, _insight_html(result),
        6, _package_html(result.package, result.warnings),
        7, result.package.model_dump_json(indent=2),
        8, gr.update(interactive=True),
        9, gr.update(interactive=True),
        10, gr.update(interactive=True),
        11, result.package.model_dump(),
        12, "",
        13, _tracker_rows(),
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
        return gr.update(), "Nothing to approve.", None, gr.update(), _tracker_rows()
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
        return gr.update(), f"Cannot approve: {exc}", state, gr.update(), _tracker_rows()
    return (
        gr.update(interactive=False),
        f"Approved — package `{package.package_id}` is ready to use.",
        package.model_dump(),
        _package_html(package, []),
        _tracker_rows(),
    )


def reject(state, feedback):
    package = _load_package(state)
    if package is None:
        return gr.update(), "Nothing to reject.", None, gr.update(), _tracker_rows()
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
        return gr.update(), f"Cannot reject: {exc}", state, gr.update(), _tracker_rows()
    return (
        gr.update(interactive=False),
        f"Rejected — package `{package.package_id}` will not be used.",
        package.model_dump(),
        _package_html(package, []),
        _tracker_rows(),
    )


def request_revision(state, feedback):
    package = _load_package(state)
    if package is None:
        return gr.update(), state, "Nothing to revise.", gr.update(), _tracker_rows()
    if not (feedback or "").strip():
        return (
            gr.update(),
            state,
            "Please describe the revision you want.",
            gr.update(),
            _tracker_rows(),
        )
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
        return gr.update(), state, f"Cannot revise: {exc}", gr.update(), _tracker_rows()

    return (
        gr.update(interactive=True),
        state,
        f"Revision {outcome.revision_count} requested — update the inputs and analyze again.",
        _package_html(package, []),
        _tracker_rows(),
    )


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
# Layout
# --------------------------------------------------------------------------- #
def build_app() -> gr.Blocks:
    with gr.Blocks(title="CareerCrew — Match your resume to the role") as demo:
        state = gr.State(None)

        gr.HTML(_topbar())
        gr.HTML(_hero())

        with gr.Row(equal_height=True):
            with gr.Column(scale=1):
                with gr.Group(elem_classes=["cc-panel"]):
                    gr.HTML(
                        "<div class='cc-panel-head'><h3>Your resume</h3>"
                        "<p class='cc-hint'>Upload a file or paste the text — whichever is easier.</p></div>"
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
                                lines=14,
                                elem_classes=["cc-field"],
                                show_label=False,
                            )

            with gr.Column(scale=1):
                with gr.Group(elem_classes=["cc-panel"]):
                    gr.HTML(
                        "<div class='cc-panel-head'><h3>The job</h3>"
                        "<p class='cc-hint'>Paste the posting, or fetch it from a secure https link.</p></div>"
                    )
                    sample_jd_btn = gr.Button("Try a sample job", size="sm")
                    with gr.Tabs():
                        with gr.Tab("Paste posting"):
                            jd_text = gr.Textbox(
                                label="Job description",
                                placeholder="Paste the job description here…",
                                lines=12,
                                elem_classes=["cc-field"],
                                show_label=False,
                            )
                        with gr.Tab("From URL"):
                            jd_url = gr.Textbox(
                                label="Job posting URL",
                                placeholder="https://company.com/jobs/…",
                                elem_classes=["cc-field"],
                            )
                    with gr.Accordion("Optional screening questions", open=False):
                        screening_text = gr.Textbox(
                            label="One question per line",
                            placeholder="Are you authorized to work in the US?\nWhat is your notice period?",
                            lines=3,
                            elem_classes=["cc-field"],
                            show_label=False,
                        )

        with gr.Group(elem_classes=["cc-cta"]):
            with gr.Row():
                with gr.Column(scale=3):
                    gr.HTML(
                        "<div class='cc-cta-copy'><h3>Ready when you are</h3>"
                        "<p>We’ll score the match, suggest stronger bullets, and prepare honest "
                        "screening answers.</p></div>"
                    )
                with gr.Column(scale=2):
                    with gr.Row():
                        run_btn = gr.Button(
                            "Analyze match", variant="primary", elem_classes=["cc-run"], scale=3
                        )
                        clear_btn = gr.Button("Clear", size="sm", scale=1)

        banner = gr.HTML(_mode_banner())
        stages_html = gr.HTML(_stages_html(-1))
        status = gr.Markdown(_IDLE_STATUS)
        error_box = gr.Markdown(visible=False)

        with gr.Tabs():
            with gr.Tab("Match report"):
                insight_html = gr.HTML(_insight_html(None))
            with gr.Tab("Application package"):
                package_md = gr.HTML(_package_html(None))
            with gr.Tab("History"):
                tracker_table = gr.Dataframe(
                    headers=["Package", "Role", "Company", "Status", "Revisions", "Updated"],
                    datatype=["str"] * 6,
                    interactive=False,
                    label="Your recent packages",
                    value=_tracker_rows(),
                )
            with gr.Tab("Advanced"):
                with gr.Accordion("Step-by-step log", open=True):
                    trace_md = gr.Markdown(_trace_markdown(None))
                with gr.Accordion("Raw package JSON", open=False):
                    package_json = gr.Code(label="Package JSON", language="json")

        with gr.Group(elem_classes=["cc-review"]):
            gr.HTML(
                "<div class='cc-panel-head'><h3>Your decision</h3>"
                "<p class='cc-hint'>Nothing is finalized until you approve it.</p></div>"
            )
            feedback = gr.Textbox(
                label="Notes for a revision (required if you request changes)",
                placeholder="e.g. Drop the AWS bullet — it’s not backed by my resume.",
                lines=2,
            )
            with gr.Row():
                approve_btn = gr.Button("Approve package", variant="primary", interactive=False)
                revise_btn = gr.Button("Request changes", interactive=False)
                reject_btn = gr.Button("Reject", variant="stop", interactive=False)
            review_status = gr.Markdown("")
            refresh_btn = gr.Button("Refresh history", size="sm")

        gr.HTML(
            "<p class='cc-foot'>CareerCrew keeps screening answers honest — verified facts only, "
            "and anything uncertain is left for you to answer.</p>"
        )

        # --- wiring --------------------------------------------------------- #
        analyze_outputs = [
            error_box,       # 0
            status,          # 1
            banner,          # 2
            stages_html,     # 3
            trace_md,        # 4
            insight_html,    # 5
            package_md,      # 6
            package_json,    # 7
            approve_btn,     # 8
            reject_btn,      # 9
            revise_btn,      # 10
            state,           # 11
            feedback,        # 12
            tracker_table,   # 13
        ]

        run_btn.click(
            analyze,
            inputs=[resume_file, resume_text, jd_text, jd_url, screening_text],
            outputs=analyze_outputs,
        )

        clear_btn.click(
            lambda: (
                gr.update(value=None),
                gr.update(value=""),
                gr.update(value=""),
                gr.update(value=""),
                gr.update(value=""),
                *_empty_outputs(),
            ),
            outputs=[resume_file, resume_text, jd_text, jd_url, screening_text, *analyze_outputs],
        )

        sample_resume_btn.click(
            lambda: (gr.update(value=None), gr.update(value=_read_sample("sample_resume.txt"))),
            outputs=[resume_file, resume_text],
        )
        sample_jd_btn.click(
            lambda: (
                gr.update(value=_read_sample("sample_jd.txt")),
                gr.update(value=""),
                gr.update(value=_SAMPLE_QUESTIONS),
            ),
            outputs=[jd_text, jd_url, screening_text],
        )

        approve_btn.click(
            approve,
            inputs=[state, feedback],
            outputs=[approve_btn, review_status, state, package_md, tracker_table],
        )
        reject_btn.click(
            reject,
            inputs=[state, feedback],
            outputs=[reject_btn, review_status, state, package_md, tracker_table],
        )
        revise_btn.click(
            request_revision,
            inputs=[state, feedback],
            outputs=[revise_btn, state, review_status, package_md, tracker_table],
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
