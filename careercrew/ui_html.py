"""Turn pipeline data into HTML for the Gradio page.

What it does: builds the progress tracker, match report, prep plan, and review guide.
Who calls it: app.py for the first paint, and the Analyze callbacks for live updates.
What it returns: HTML strings. No Gradio state lives here.
"""

from __future__ import annotations

import html

from careercrew.config import get_settings
from careercrew.models import InterviewPrepPlan
from careercrew.runner import FINAL_STAGE as _FINAL
from careercrew.runner import STAGES
from careercrew.runner import TOTAL_STAGES as _TOTAL_STAGES


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


def _topbar() -> str:
    chip = (
        "<div class='cc-status-chip'><span class='dot'></span>Ready</div>"
        if get_settings().has_llm
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
        "<p class='cc-sub'>Use the tabs below in order: run <strong>Analyze match</strong>, "
        "then the prep coach, then the mock interview, then the post-interview coach. "
        "Progress and decisions stay inside Analyze — they won’t clutter the other steps.</p></div>"
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
            f"<div class='cc-live'><span class='cc-blink'>●</span><span>{_esc(detail)}</span></div>"
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
            parts.append(
                f"<div style='font-weight:700;font-size:15px'>{_esc(profile.full_name)}</div>"
            )
        if profile.summary:
            parts.append(
                f"<p style='color:var(--cc-ink-2);font-size:13.5px;margin:6px 0;line-height:1.55'>{_esc(profile.summary)}</p>"
            )
        if profile.skills:
            chips = "".join(
                f"<span class='cc-chip'>{_esc(skill)}</span>" for skill in profile.skills
            )
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
        parts.append(f"<p class='cc-hint' style='margin-top:10px'>{_esc(seniority.rationale)}</p>")

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


def _review_guide_html(phase: str = "idle", *, package_id: str = "", detail: str = "") -> str:
    """Step-by-step guide for the HITL decision dock.

    ``phase``: idle | ready | working | approved | rejected
    """
    steps = [
        (1, "Upload resume + JD above, then press Analyze match"),
        (2, "Open the result sub-tabs (Match / Prep)"),
        (3, "Decide below — approve, add missing experience, or reject"),
    ]
    if phase == "idle":
        active = 1
        blurb = (
            "Unlocks after Analyze finishes in this tab. Nothing here is submitted to an employer."
        )
    elif phase == "working":
        active = 3
        blurb = detail or ("Applying your experience updates and re-running Analyze automatically…")
    elif phase == "approved":
        active = 3
        blurb = (
            f"Approved{f' — `{_esc(package_id)}`' if package_id else ''}. "
            "Next: Interview prep plan, Prep coach, or Mock interview."
        )
    elif phase == "rejected":
        active = 3
        blurb = (
            f"Rejected{f' — `{_esc(package_id)}`' if package_id else ''}. "
            "Update the resume or job above and Analyze again for a new bundle."
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
