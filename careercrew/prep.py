"""CareerCrew - Interview Preparation Advisor.

Turns the honest gap analysis into a seniority-aware study plan: which areas
deserve the most preparation time, why, and what to practice. Works in two
modes:

* ``build_prep_plan`` runs the Interview Prep Advisor agent (used by the crew).
* ``build_fallback_plan`` derives the same structure deterministically from the
  gap verdicts, so the Prep tab is always populated even without an LLM key.

Both modes follow the same rule: priorities come from the gap verdicts, and
every focus area cites the requirement it is based on.
"""

from __future__ import annotations

import logging

from careercrew.models import (
    GapReport,
    InterviewPrepPlan,
    JobRequirements,
    PrepFocus,
    SeniorityAssessment,
    SeniorityBand,
    seniority_band_from_label,
)

logger = logging.getLogger("careercrew.prep")

#: Share of prep time suggested for each gap class (percent, before normalising).
_SHARE_BY_VERDICT = {"out_of_scope": 45, "reframeable": 30, "covered": 15}


def _verdict_class(verdict: str) -> str:
    key = (verdict or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key.startswith("reframe"):
        return "reframeable"
    if key.startswith("out"):
        return "out_of_scope"
    return "covered"


#: Extra practice emphasis that the target seniority band adds.
_BAND_EMPHASIS: dict[SeniorityBand, list[str]] = {
    SeniorityBand.EARLY: [
        "Fundamentals and clear explanation of hands-on work",
        "Willingness to learn and how you pick up new tools",
    ],
    SeniorityBand.MID: [
        "Ownership and measurable impact of your projects",
        "Cross-team collaboration and delivery under constraints",
    ],
    SeniorityBand.SENIOR: [
        "System and organizational design trade-offs",
        "Influence, mentoring, and driving outcomes across teams",
    ],
}


def _band_assessment(
    requested: str, profile, requirements: JobRequirements
) -> SeniorityAssessment:
    band = seniority_band_from_label(requested or requirements.seniority)
    seen: set[str] = set()
    for role in profile.experience:
        dates = (role.dates or "").strip()
        if dates and dates not in seen:
            seen.add(dates)
    detected = f"{len(profile.experience)} role(s) listed" if profile.experience else ""
    confidence = 55 if detected else 25
    if requirements.seniority:
        confidence = min(95, confidence + 20)
    return SeniorityAssessment(
        band=band,
        target_years=band.label,
        detected_years=detected,
        confidence=confidence,
        rationale=(
            f"Plan calibrated for the {band.label} experience band"
            + (f"; the posting signals '{requirements.seniority}'." if requirements.seniority else ".")
        ),
    )


def build_fallback_plan(
    profile,
    requirements: JobRequirements,
    gaps: GapReport,
    requested_seniority: str = "",
) -> InterviewPrepPlan:
    """Derive a grounded prep plan directly from the gap verdicts."""
    seniority = _band_assessment(requested_seniority, profile, requirements)

    focus: list[PrepFocus] = []
    strengths: list[str] = []
    risks: list[str] = []
    themes: list[str] = []

    for verdict in gaps.verdicts:
        cls = _verdict_class(verdict.verdict)
        if cls == "out_of_scope":
            priority = "high"
            risks.append(verdict.requirement)
            why = (
                "No supporting experience in the resume. Prepare an honest way to "
                "address it: adjacent work, a concrete learning plan, or a clear "
                "scope-limit answer."
            )
        elif cls == "reframeable":
            priority = "medium"
            why = (
                "You have related experience. Practice turning it into a clear "
                "transferable story tied to this requirement."
            )
        else:
            priority = "low"
            strengths.append(verdict.requirement)
            why = "Already covered by your resume. Rehearse a short, crisp example."
        focus.append(
            PrepFocus(
                area=verdict.requirement,
                priority=priority,
                suggested_share_pct=_SHARE_BY_VERDICT.get(cls, 10),
                why=why,
                evidence=verdict.requirement,
            )
        )

    # Highest priority first so the UI leads with the biggest gaps.
    order = {"high": 0, "medium": 1, "low": 2}
    focus.sort(key=lambda item: order.get(item.priority, 3))

    # Normalise the shares so they total roughly 100.
    total = sum(item.suggested_share_pct for item in focus) or 0
    if total:
        for item in focus:
            item.suggested_share_pct = max(1, round(item.suggested_share_pct * 100 / total))

    themes.extend(_BAND_EMPHASIS.get(seniority.band, []))
    for verdict in gaps.verdicts[:5]:
        themes.append(f"Tell me about your experience with {verdict.requirement}.")

    return InterviewPrepPlan(
        seniority=seniority,
        focus_areas=focus,
        question_themes=themes,
        strengths=strengths,
        risk_areas=risks,
    )


def build_prep_plan(
    profile,
    requirements: JobRequirements,
    gaps: GapReport,
    requested_seniority: str = "",
    *,
    llm=None,
) -> InterviewPrepPlan:
    """Build the prep plan, preferring an LLM agent when one is available.

    ``llm`` is an optional callable ``llm(prompt) -> str`` (JSON). When it is
    missing or fails, the deterministic gap-based plan is used, so the Prep tab
    is never empty and never fabricated.
    """
    fallback = build_fallback_plan(profile, requirements, gaps, requested_seniority)
    if llm is None:
        return fallback
    try:
        prompt = _build_prompt(profile, requirements, gaps, requested_seniority)
        raw = llm(prompt)
    except Exception as exc:  # noqa: BLE001 - never break the run over the advisor
        logger.warning("prep advisor LLM failed: %s", exc)
        return fallback
    return merge_plan(raw, fallback)


def _build_prompt(profile, requirements: JobRequirements, gaps: GapReport, requested: str) -> str:
    band = seniority_band_from_label(requested or requirements.seniority)
    return (
        "You are the Interview Preparation Advisor. Build an interview prep plan "
        f"for a candidate targeting the {band.label} band.\n"
        "Use ONLY the resume facts, job requirements, and gap verdicts below. "
        "Return ONLY JSON matching:\n"
        '{"seniority": {"band": "early|mid|senior", "target_years": str, '
        '"detected_years": str, "confidence": int, "rationale": str}, '
        '"focus_areas": [{"area": str, "priority": "high|medium|low", '
        '"suggested_share_pct": int, "why": str, "evidence": str}], '
        '"question_themes": [str], "strengths": [str], "risk_areas": [str]}\n'
        "Rank focus areas by risk; out_of_scope gaps are highest priority. "
        "Suggested shares should total about 100.\n\n"
        f"PROFILE:\n{profile.model_dump_json()}\n\n"
        f"REQUIREMENTS:\n{requirements.model_dump_json()}\n\n"
        f"GAPS:\n{gaps.model_dump_json()}\n"
    )


def merge_plan(raw: str, fallback: InterviewPrepPlan) -> InterviewPrepPlan:
    """Parse the advisor JSON, falling back per-field on anything unusable."""
    from careercrew.pipeline import extract_json

    data = extract_json(raw)
    if not isinstance(data, dict):
        return fallback
    try:
        parsed = InterviewPrepPlan.model_validate(data)
    except Exception:  # noqa: BLE001 - bounded repair
        return fallback
    if not parsed.focus_areas:
        parsed.focus_areas = fallback.focus_areas
    if not parsed.seniority.rationale:
        parsed.seniority = fallback.seniority
    if not parsed.question_themes:
        parsed.question_themes = fallback.question_themes
    return parsed
