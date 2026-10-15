"""CareerCrew - Gradio web interface.

A single page that drives the whole workflow:

1. Provide a resume (upload a PDF/DOCX/TXT file **or** paste the text) and a job
   description (paste text or an https URL).
2. Optionally paste employer screening questions.
3. Press **Run analysis** to run the five-agent crew through real MCP tools.
4. Watch the **live stage tracker**: the UI shows exactly which stage of the
   pipeline is executing, which agent is working, and what it is doing.
5. Read the coverage/gap report, the cited feedback draft, and the assembled
   application package.
6. **Approve**, **Reject**, or **Request revision** (with feedback).
7. See the session tracker of packages prepared so far.

The UI never fabricates an analysis: with no LLM key it falls back to real MCP
screening-answer retrieval and says so. A JD URL that cannot be accessed is
shown as a clean error instead of crashing.
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
    "Ready when you are. Add a resume and a job description, then press "
    "**Run analysis** to watch the five agents work stage by stage."
)

# --------------------------------------------------------------------------- #
# Pipeline stages (mirror careercrew/pipeline.py) and the CSS design system
# --------------------------------------------------------------------------- #
STAGES: list[tuple[int, str, str]] = [
    (1, "Validate inputs", "Guardrails check type, size, PII, and injection patterns"),
    (2, "Extract profile", "Profile Extractor reads the resume via MCP read_resume"),
    (3, "Analyze the job", "JD Analyzer fetches the JD via MCP fetch_job_description"),
    (4, "Score coverage", "Gap Analyst labels each requirement covered / reframeable / out of scope"),
    (5, "Draft feedback", "Feedback Writer produces cited bullet rewrites and talking points"),
    (6, "Assemble package", "Application Packager answers questions via MCP query_answer_bank"),
    (7, "Validate output", "Output guardrails verify the package, then it awaits your review"),
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
_AGENT_LABEL = {
    2: "Profile Extractor",
    3: "JD Analyzer",
    4: "Gap Analyst",
    5: "Feedback Writer",
    6: "Application Packager",
}

CUSTOM_CSS = """
/* Design tokens. Light values first; `body.dark` (Gradio sets this class when the
   viewer's browser is in dark mode) overrides them so the whole UI is adaptive. */
:root {
  --cc-bg: #f6f7fb;
  --cc-surface: #ffffff;
  --cc-surface-2: #fbfcfe;
  --cc-line: #e6e8f0;
  --cc-ink: #0f172a;
  --cc-ink-2: #334155;
  --cc-muted: #64748b;
  --cc-soft: #f1f5f9;
  --cc-accent: #4f46e5;
  --cc-accent-2: #7c3aed;
  --cc-ok: #16a34a;
  --cc-warn: #d97706;
  --cc-bad: #dc2626;
  --cc-shadow: rgba(15, 23, 42, .45);
}
body.dark {
  --cc-bg: #0a0f1e;
  --cc-surface: #172136;
  --cc-surface-2: #1b2740;
  --cc-line: #334155;
  --cc-ink: #f1f5f9;
  --cc-ink-2: #cbd5e1;
  --cc-muted: #94a3b8;
  --cc-soft: #1e293b;
  --cc-accent: #818cf8;
  --cc-accent-2: #a78bfa;
  --cc-ok: #4ade80;
  --cc-warn: #fbbf24;
  --cc-bad: #f87171;
  --cc-shadow: rgba(0, 0, 0, .6);
}

/* ------------------------------------------------------------------ shell -- */
.gradio-container {
  max-width: 1320px !important;
  margin: 0 auto !important;
  background:
    radial-gradient(1100px 460px at 8% -12%, color-mix(in srgb, var(--cc-accent) 12%, transparent), transparent 60%),
    radial-gradient(900px 420px at 100% -6%, color-mix(in srgb, var(--cc-accent-2) 10%, transparent), transparent 55%),
    var(--cc-bg) !important;
  color: var(--cc-ink) !important;
}
footer { display: none !important; }

/* Gradio renders each block's label as a pill; keep it a quiet caption. */
[data-testid="block-info"] {
  background: transparent !important;
  border: none !important;
  color: var(--cc-muted) !important;
  font-size: 12.5px !important;
  font-weight: 650 !important;
  letter-spacing: .01em !important;
  padding: 0 !important;
  margin-bottom: 6px !important;
}

.cc-hero {
  border: 1px solid var(--cc-line);
  border-radius: 20px;
  padding: 24px 26px;
  background: linear-gradient(135deg, color-mix(in srgb, var(--cc-accent) 16%, transparent),
              color-mix(in srgb, var(--cc-accent-2) 8%, transparent) 60%, transparent), var(--cc-surface);
  box-shadow: 0 18px 40px -28px var(--cc-shadow);
  margin-bottom: 10px;
}
.cc-hero h1 { margin: 0 0 6px 0; font-size: 30px; letter-spacing: -0.02em; font-weight: 750; color: var(--cc-ink); }
.cc-hero .cc-sub { color: var(--cc-ink-2); font-size: 14.5px; margin: 0 0 14px 0; max-width: 92ch; line-height: 1.6; }
.cc-badges { display: flex; flex-wrap: wrap; gap: 8px; }
.cc-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 11px; border-radius: 999px; font-size: 12px;
  font-weight: 650; letter-spacing: .01em; border: 1px solid transparent;
}
.cc-badge.ghost { background: var(--cc-soft); color: var(--cc-ink-2); border-color: var(--cc-line); }
.cc-badge.on  { background: color-mix(in srgb, var(--cc-accent) 16%, transparent); color: var(--cc-accent); border-color: color-mix(in srgb, var(--cc-accent) 38%, transparent); }
.cc-badge.off { background: color-mix(in srgb, var(--cc-warn) 16%, transparent); color: var(--cc-warn); border-color: color-mix(in srgb, var(--cc-warn) 38%, transparent); }
.cc-badge.covered { background: color-mix(in srgb, var(--cc-ok) 16%, transparent); color: var(--cc-ok); border-color: color-mix(in srgb, var(--cc-ok) 38%, transparent); }
.cc-badge.reframeable { background: color-mix(in srgb, var(--cc-warn) 16%, transparent); color: var(--cc-warn); border-color: color-mix(in srgb, var(--cc-warn) 38%, transparent); }
.cc-badge.out { background: color-mix(in srgb, var(--cc-bad) 16%, transparent); color: var(--cc-bad); border-color: color-mix(in srgb, var(--cc-bad) 38%, transparent); }
.cc-badge.src { background: var(--cc-soft); color: var(--cc-ink-2); border-color: var(--cc-line); font-family: ui-monospace, monospace; }

.cc-card {
  border: 1px solid var(--cc-line);
  border-radius: 16px;
  background: var(--cc-surface);
  padding: 18px 20px;
  box-shadow: 0 12px 30px -26px var(--cc-shadow);
}
.cc-card h3 { margin: 0 0 4px 0; font-size: 15px; font-weight: 700; color: var(--cc-ink); letter-spacing: -0.01em; }
.cc-card .cc-hint { color: var(--cc-muted); font-size: 13px; margin: 0 0 12px 0; }
.cc-empty {
  border: 1px dashed color-mix(in srgb, var(--cc-line) 90%, transparent);
  border-radius: 14px; padding: 20px;
  color: var(--cc-muted); background: var(--cc-surface-2); font-size: 13px; line-height: 1.55;
}

/* --------------------------------------------------- inputs panel polish --- */
.cc-panel {
  border: 1px solid var(--cc-line) !important;
  border-radius: 18px !important;
  background: var(--cc-surface) !important;
  padding: 4px 6px 8px 6px !important;
  box-shadow: 0 12px 30px -26px var(--cc-shadow);
}
.cc-panel-head h3 {
  margin: 4px 0 2px 0; font-size: 16px; font-weight: 720; color: var(--cc-ink);
  letter-spacing: -0.01em;
}
.cc-panel-head .cc-hint { color: var(--cc-muted); font-size: 13px; margin: 0 0 10px 0; }
.cc-subhead {
  display: flex; align-items: center; gap: 7px; margin: 14px 0 2px 0;
  font-size: 12px; font-weight: 750; text-transform: uppercase; letter-spacing: .08em;
  color: var(--cc-muted);
}
.cc-subhead .cc-num {
  display: inline-grid; place-items: center; width: 18px; height: 18px; border-radius: 50%;
  background: color-mix(in srgb, var(--cc-accent) 18%, transparent); color: var(--cc-accent);
  font-size: 11px; font-weight: 800;
}
.cc-field textarea, .cc-field input[type="text"], .cc-field input[type="url"] {
  background: var(--cc-soft) !important;
  color: var(--cc-ink) !important;
  border: 1px solid var(--cc-line) !important;
  border-radius: 12px !important;
}
.cc-field textarea::placeholder, .cc-field input::placeholder { color: var(--cc-muted) !important; opacity: .85; }
.cc-actions { align-items: stretch; }

/* ------------------------------------------------------- live stage tracker -- */
.cc-stages { display: flex; flex-direction: column; gap: 8px; }
.cc-stage {
  display: grid; grid-template-columns: 34px 1fr auto; gap: 12px;
  align-items: center;
  border: 1px solid var(--cc-line); border-left: 4px solid var(--cc-line);
  border-radius: 12px; padding: 12px 14px; background: var(--cc-surface-2);
  transition: box-shadow .18s ease, border-color .18s ease, transform .18s ease;
}
.cc-stage .cc-dot {
  width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center;
  font-size: 13px; font-weight: 700; background: var(--cc-soft); color: var(--cc-muted);
}
.cc-stage .cc-ttl { font-weight: 650; font-size: 14px; color: var(--cc-ink); }
.cc-stage .cc-blurb { font-size: 12.5px; color: var(--cc-muted); margin-top: 1px; }
.cc-stage .cc-pill {
  font-size: 10.5px; font-weight: 750; letter-spacing: .06em;
  padding: 4px 9px; border-radius: 999px; background: var(--cc-soft); color: var(--cc-muted);
}
.cc-stage.done { border-left-color: var(--cc-ok); background: color-mix(in srgb, var(--cc-ok) 8%, var(--cc-surface)); }
.cc-stage.done .cc-dot,
.cc-stage.done .cc-pill { background: color-mix(in srgb, var(--cc-ok) 18%, transparent); color: var(--cc-ok); }
.cc-stage.active {
  border-left-color: var(--cc-accent);
  background: color-mix(in srgb, var(--cc-accent) 7%, var(--cc-surface));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--cc-accent) 16%, transparent), 0 14px 30px -24px var(--cc-accent);
  transform: translateX(1px);
}
.cc-stage.active .cc-dot,
.cc-stage.active .cc-pill { background: color-mix(in srgb, var(--cc-accent) 20%, transparent); color: var(--cc-accent); }
.cc-stage.active .cc-dot { animation: cc-pulse 1.2s infinite; }
@keyframes cc-pulse { 0%,100% { opacity: 1 } 50% { opacity: .45 } }
.cc-live {
  margin-top: 12px; border-radius: 12px; padding: 11px 13px;
  background: var(--cc-soft); border: 1px solid var(--cc-line);
  color: var(--cc-ink-2); font-size: 12.5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  display: flex; align-items: center; gap: 8px;
}
.cc-live .cc-blink { color: var(--cc-accent); animation: cc-pulse 1.1s infinite; }

/* --------------------------------------------------- coverage meter + tables -- */
.cc-meter { margin: 6px 0 18px 0; }
.cc-meter .cc-meter-top { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 7px; }
.cc-meter .cc-score { font-size: 26px; font-weight: 780; letter-spacing: -0.02em; color: var(--cc-ink); }
.cc-meter .cc-score small { font-size: 13px; color: var(--cc-muted); font-weight: 600; }
.cc-meter .cc-meter-label { font-size: 12px; color: var(--cc-muted); text-transform: uppercase; letter-spacing: .08em; font-weight: 700; text-align: right; }
.cc-bar { height: 12px; border-radius: 999px; background: var(--cc-soft); overflow: hidden; }
.cc-bar > span { display: block; height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, var(--cc-accent), var(--cc-accent-2) 60%, #06b6d4); }
.cc-stats { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 11px; }
.cc-chip {
  font-size: 12px; font-weight: 650; padding: 5px 10px; border-radius: 999px;
  background: var(--cc-soft); color: var(--cc-ink-2); border: 1px solid var(--cc-line);
}
.cc-chip.covered { background: color-mix(in srgb, var(--cc-ok) 16%, transparent); color: var(--cc-ok); border-color: color-mix(in srgb, var(--cc-ok) 38%, transparent); }
.cc-chip.reframeable { background: color-mix(in srgb, var(--cc-warn) 16%, transparent); color: var(--cc-warn); border-color: color-mix(in srgb, var(--cc-warn) 38%, transparent); }
.cc-chip.out { background: color-mix(in srgb, var(--cc-bad) 16%, transparent); color: var(--cc-bad); border-color: color-mix(in srgb, var(--cc-bad) 38%, transparent); }

.cc-section-title {
  font-size: 12px; font-weight: 750; text-transform: uppercase; letter-spacing: .08em;
  color: var(--cc-muted); margin: 20px 0 10px 0;
}
.cc-table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
.cc-table th {
  text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
  color: var(--cc-muted); padding: 8px 10px; border-bottom: 1px solid var(--cc-line);
}
.cc-table td { padding: 10px; border-bottom: 1px solid var(--cc-line); vertical-align: top; color: var(--cc-ink-2); }
.cc-table tbody tr:hover td { background: color-mix(in srgb, var(--cc-accent) 6%, transparent); }

.cc-bullets { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; }
.cc-bullets li { border: 1px solid var(--cc-line); border-radius: 12px; padding: 12px 14px; background: var(--cc-surface-2); }
.cc-bullets li p { margin: 0 0 7px 0; color: var(--cc-ink); font-size: 14px; line-height: 1.55; }
.cc-cite { font-size: 12px; color: var(--cc-muted); }
.cc-cite b { color: var(--cc-accent); }
.cc-list { margin: 0; padding-left: 18px; color: var(--cc-ink-2); font-size: 13.5px; line-height: 1.65; }
.cc-note {
  border: 1px solid color-mix(in srgb, var(--cc-warn) 38%, transparent);
  background: color-mix(in srgb, var(--cc-warn) 12%, transparent); color: var(--cc-warn);
  border-radius: 12px; padding: 11px 13px; font-size: 13px; margin-top: 10px;
}
.cc-note .cc-list { color: var(--cc-ink-2); }
.cc-foot { color: var(--cc-muted); font-size: 12px; margin-top: 8px; text-align: center; }

button.cc-run {
  background: linear-gradient(135deg, var(--cc-accent), var(--cc-accent-2)) !important;
  border: none !important; color: #fff !important; font-weight: 700 !important;
  box-shadow: 0 12px 26px -14px color-mix(in srgb, var(--cc-accent) 85%, transparent) !important;
  min-height: 44px;
}
"""


# --------------------------------------------------------------------------- #
# Small rendering helpers
# --------------------------------------------------------------------------- #
def _esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""))


def _mode_banner() -> str:
    if _SETTINGS.has_llm:
        return (
            "<div class='cc-card' style='padding:14px 16px'>"
            "<span class='cc-badge on'>AGENTS ENABLED</span> "
            "<span class='cc-hint' style='margin:0'>The five-agent crew runs through real MCP "
            f"tools on <b>{_esc(_SETTINGS.openai_model)}</b>.</span></div>"
        )
    return (
        "<div class='cc-card' style='padding:14px 16px'>"
        "<span class='cc-badge off'>FALLBACK MODE</span> "
        "<span class='cc-hint' style='margin:0'>No OPENAI_API_KEY is set. Screening answers are "
        "still retrieved through real MCP calls and shown honestly; add a key for the full crew."
        "</span></div>"
    )


def _hero(mode_label: str) -> str:
    return (
        "<div class='cc-hero'>"
        "<h1>CareerCrew</h1>"
        "<p class='cc-sub'>A multi-agent resume, interview, and job-application coach built on "
        "CrewAI and the Model Context Protocol. Five agents extract your profile, analyze the "
        "role, score coverage, draft cited bullets, and assemble an application package whose "
        "screening answers come only from a verified answer bank.</p>"
        "<div class='cc-badges'>"
        "<span class='cc-badge ghost'>CrewAI · sequential</span>"
        "<span class='cc-badge ghost'>MCP · 3 real tools</span>"
        "<span class='cc-badge ghost'>Knowledge · resume guidelines</span>"
        "<span class='cc-badge ghost'>Guardrails · in / out</span>"
        "<span class='cc-badge ghost'>Human-in-the-loop</span>"
        f"<span class='cc-badge ghost'>{_esc(mode_label)}</span>"
        "</div></div>"
    )


def _stages_html(current: int = -1, detail: str = "") -> str:
    """Render the live stage tracker.

    ``current`` is the stage number that is executing: lower numbers are done,
    the current one is active, higher numbers are queued. ``current`` greater
    than the number of stages marks everything complete; ``-1`` means idle.
    """
    rows: list[str] = []
    for number, title, blurb in STAGES:
        if current < 0:
            cls, icon, pill = "", "○", "READY"
        elif number < current:
            cls, icon, pill = "done", "✓", "DONE"
        elif number == current:
            cls, icon, pill = "active", "◐", "RUNNING"
        else:
            cls, icon, pill = "", "○", "QUEUED"
        agent = _AGENT_LABEL.get(number)
        agent_html = f" · <b>{_esc(agent)}</b>" if agent else ""
        rows.append(
            f"<div class='cc-stage {cls}'>"
            f"<div class='cc-dot'>{icon}</div>"
            f"<div><div class='cc-ttl'>{number}. {_esc(title)}{agent_html}</div>"
            f"<div class='cc-blurb'>{_esc(blurb)}</div></div>"
            f"<div class='cc-pill'>{pill}</div>"
            "</div>"
        )
    live = ""
    if detail:
        live = (
            "<div class='cc-live'><span class='cc-blink'>▸</span>"
            f"<span>{_esc(detail)}</span></div>"
        )
    header = (
        "<div class='cc-card'><h3>Live pipeline</h3>"
        f"<p class='cc-hint'>Stage {max(current, 0)} of {_TOTAL_STAGES} · "
        "the tracker advances as each agent starts and finishes.</p>"
        "<div class='cc-stages'>"
    )
    return header + "".join(rows) + "</div>" + live + "</div>"


def _empty_card(title: str, hint: str) -> str:
    return (
        f"<div class='cc-card'><h3>{_esc(title)}</h3>"
        f"<div class='cc-empty'>{_esc(hint)}</div></div>"
    )


def _trace_markdown(result) -> str:
    if not result:
        return (
            "**Execution trace**\n\n"
            "1. Input guardrails validate the resume and job description.\n"
            "2. Profile Extractor reads the resume via MCP `read_resume`.\n"
            "3. JD Analyzer reads the job description via MCP `fetch_job_description`.\n"
            "4. Gap Analyst scores coverage and labels each requirement.\n"
            "5. Feedback Writer drafts cited bullets and talking points.\n"
            "6. Application Packager answers screening questions via MCP `query_answer_bank`.\n"
            "7. Output guardrails validate the package, then it awaits your review."
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
            "Coverage & insights",
            "Run an analysis to see the keyword coverage meter, per-requirement verdicts, "
            "the candidate profile, the extracted requirements, and the rewrite plan.",
        )

    gaps = result.gaps
    score = max(0, min(100, int(gaps.coverage_score)))
    verdicts = gaps.verdicts
    counts = {"covered": 0, "reframeable": 0, "out": 0}
    for verdict in verdicts:
        counts[_verdict_class(verdict.verdict)] += 1

    parts: list[str] = ["<div class='cc-card'>"]
    parts.append("<h3>Coverage score</h3>")
    parts.append("<p class='cc-hint'>Share of the role's requirements the resume genuinely covers.</p>")
    label = "Keyword &amp; skill match" if verdicts else "No verdicts returned"
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
        parts.append("<div class='cc-section-title'>Candidate profile</div>")
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
        parts.append("<div class='cc-section-title'>Role requirements</div>")
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
        parts.append("<div class='cc-section-title'>Requirement verdicts</div>")
        parts.append(
            "<table class='cc-table'><thead><tr><th>Requirement</th><th>Verdict</th>"
            "<th>Supporting fact</th></tr></thead><tbody>"
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
        parts.append("<div class='cc-section-title'>Rewrite plan — every bullet is cited</div>")
        bullets = "".join(
            "<li>"
            f"<p>{_esc(bullet.text)}</p>"
            f"<div class='cc-cite'>cited from: <b>{_esc(bullet.cited_fact) or '—'}</b></div>"
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


def _package_markdown(package: ApplicationPackage | None, warnings: list[str] | None = None) -> str:
    """The assembled application package (screening answers + items needing input)."""
    if package is None:
        return (
            "### Application package\n\n"
            "_The assembled package will appear here after analysis. Every screening answer "
            "is sourced from the verified answer bank (`answer_bank`); anything unverified is "
            "listed under items needing your input instead of being invented._"
        )
    lines = [
        "### Application package",
        "",
        f"`{package.package_id}` · role: **{package.role_title or '—'}** · "
        f"company: **{package.company or '—'}**",
        "",
    ]
    if package.package_summary:
        lines += [package.package_summary, ""]

    lines.append(f"#### Screening answers ({len(package.screening_answers)})")
    if package.screening_answers:
        for index, answer in enumerate(package.screening_answers, start=1):
            lines.append(
                f"**Q{index}. {answer.question}**  \n"
                f"{answer.answer}  \n"
                f"`source: {answer.source}` · verified: {'yes' if answer.verified else 'no'}"
            )
            lines.append("")
    else:
        lines += ["_No screening questions were answered from the verified bank._", ""]

    if package.do_not_claim:
        lines.append(f"#### Needs your input ({len(package.do_not_claim)})")
        lines.extend(f"- {item}" for item in package.do_not_claim)
        lines.append("")

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
        _package_markdown(None),  # package_md
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
        1, "Starting — validating inputs…",
        3, _stages_html(1, "Input guardrails: type, size, PII redaction, injection screen"),
    )

    stages: dict[str, object] = {"index": 1, "detail": "Input guardrails…"}

    def progress(message: str) -> None:
        """Bridge the pipeline's progress messages onto the stage tracker."""
        lowered = message.lower()
        if "crew output unavailable" in lowered or "direct mcp calls" in lowered:
            stages["index"], stages["detail"] = 6, message
        elif "five-agent crew" in lowered:
            stages["index"], stages["detail"] = 2, "Starting the five-agent crew…"
        else:
            stages["detail"] = message

    def on_task(output) -> None:
        """CrewAI task callback: refine the tracker after each task completes."""
        name = getattr(output, "name", "") or ""
        agent = getattr(output, "agent", "") or ""
        stage = _AGENT_STAGE.get(agent) or _TASK_STAGE.get(name)
        if stage:
            label = agent or name
            stages["index"] = stage + 1
            stages["detail"] = f"✓ {label} finished — handing off"

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

    mode = " · fallback path used" if result.used_fallback else ""
    status = (
        f"**Draft ready for review** — package `{result.package.package_id}`, "
        f"{len(result.package.screening_answers)} screening answer(s), "
        f"{len(result.package.do_not_claim)} item(s) needing your input{mode}."
    )
    yield emit(
        0, gr.update(value="", visible=False),
        1, status,
        3, _stages_html(_FINAL, "Run complete — the package is awaiting your review."),
        4, _trace_markdown(result),
        5, _insight_html(result),
        6, _package_markdown(result.package, result.warnings),
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
        f"Package `{package.package_id}` is **{outcome.status.value}**. You can now use it.",
        package.model_dump(),
        _package_markdown(package, []),
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
        f"Package `{package.package_id}` is **REJECTED**.",
        package.model_dump(),
        _package_markdown(package, []),
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
        f"Revision {outcome.revision_count} requested — update the inputs and run again.",
        _package_markdown(package, []),
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
    mode_label = "agents enabled" if _SETTINGS.has_llm else "fallback mode"

    with gr.Blocks(title="CareerCrew · Multi-Agent Application Coach") as demo:
        state = gr.State(None)

        gr.HTML(_hero(mode_label))

        with gr.Row():
            with gr.Column(scale=2):
                with gr.Group(elem_classes=["cc-panel"]):
                    gr.HTML(
                        "<div class='cc-panel-head'><h3>Start here</h3>"
                        "<p class='cc-hint'>Add a resume and a job description — then run the "
                        "five agents. Everything else is optional.</p></div>"
                    )
                    with gr.Row():
                        sample_resume_btn = gr.Button("↧  Load sample resume", size="sm")
                        sample_jd_btn = gr.Button("↧  Load sample job", size="sm")

                    gr.HTML(
                        "<div class='cc-subhead'><span class='cc-num'>1</span>"
                        "Resume — upload a file <em>or</em> paste text</div>"
                    )
                    resume_file = gr.File(
                        label="Resume file (PDF, DOCX, TXT)",
                        file_types=[".pdf", ".docx", ".txt"],
                        elem_classes=["cc-field"],
                    )
                    resume_text = gr.Textbox(
                        label="…or paste the resume text",
                        placeholder="Paste the resume text here if you do not have a file.",
                        lines=6,
                        elem_classes=["cc-field"],
                    )

                    gr.HTML(
                        "<div class='cc-subhead'><span class='cc-num'>2</span>"
                        "Job description — paste text <em>or</em> an https URL</div>"
                    )
                    jd_text = gr.Textbox(
                        label="Job description (paste text)",
                        placeholder="Paste the job description here.",
                        lines=6,
                        elem_classes=["cc-field"],
                    )
                    jd_url = gr.Textbox(
                        label="…or a job description URL (optional, https only)",
                        placeholder="https://example.com/job",
                        elem_classes=["cc-field"],
                    )

                    gr.HTML(
                        "<div class='cc-subhead'><span class='cc-num'>3</span>"
                        "Screening questions (optional)</div>"
                    )
                    screening_text = gr.Textbox(
                        label="One question per line",
                        placeholder="Are you authorized to work in the US?\nWhat is your notice period?",
                        lines=3,
                        elem_classes=["cc-field"],
                    )
                    with gr.Row(elem_classes=["cc-actions"]):
                        run_btn = gr.Button(
                            "▶  Run analysis", variant="primary", elem_classes=["cc-run"], scale=3
                        )
                        clear_btn = gr.Button("Reset", size="sm", scale=1)

            with gr.Column(scale=3):
                banner = gr.HTML(_mode_banner())
                stages_html = gr.HTML(_stages_html(-1))
                status = gr.Markdown(_IDLE_STATUS)
                error_box = gr.Markdown(visible=False)

        gr.Markdown("---")

        with gr.Tabs():
            with gr.Tab("Coverage & insights"):
                insight_html = gr.HTML(_insight_html(None))
            with gr.Tab("Application package"):
                package_md = gr.Markdown(_package_markdown(None))
            with gr.Tab("Execution trace"):
                trace_md = gr.Markdown(_trace_markdown(None))
            with gr.Tab("Package JSON"):
                package_json = gr.Code(label="ApplicationPackage", language="json")
            with gr.Tab("Session tracker"):
                tracker_table = gr.Dataframe(
                    headers=["Package", "Role", "Company", "Status", "Revisions", "Updated"],
                    datatype=["str"] * 6,
                    interactive=False,
                    label="Packages prepared in this session",
                    value=_tracker_rows(),
                )

        gr.Markdown("---")
        gr.Markdown("### Human review")
        feedback = gr.Textbox(
            label="Reviewer feedback (required to request a revision)",
            placeholder="e.g. Drop the AWS bullet — it is not backed by the resume.",
            lines=2,
        )
        with gr.Row():
            approve_btn = gr.Button("✓  Approve", variant="primary", interactive=False)
            revise_btn = gr.Button("↻  Request revision", interactive=False)
            reject_btn = gr.Button("✕  Reject", variant="stop", interactive=False)
        review_status = gr.Markdown("")
        refresh_btn = gr.Button("Refresh tracker", size="sm")

        gr.HTML(
            "<p class='cc-foot'>CareerCrew · CrewAI + MCP · every screening answer is sourced "
            "from the verified answer bank; unverified questions surface for a human, never invented.</p>"
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
