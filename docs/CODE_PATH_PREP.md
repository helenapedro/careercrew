# Code path: Interview Preparation Advisor

How CareerCrew decides **where the candidate should spend prep time**, calibrated
to the target seniority band and the resume-vs-JD gaps.

**Parent flow:** produced during [Analyze](CODE_PATH_ANALYZE.md) (agent 5 / fallback).  
**UI tab:** **Interview prep plan**.

---

## 1. Two modes (same output shape)

| Mode | When | Entry |
|------|------|-------|
| Crew agent | `OPENAI_API_KEY` set and crew parses successfully | Task `build_prep_plan` → agent `interview_prep_advisor` |
| Deterministic fallback | No key, crew fail, or `prep_plan` parse is `None` | `prep.build_fallback_plan(...)` from [`careercrew/prep.py`](../careercrew/prep.py) |

Both must:

- Tie every focus area to a real requirement / gap evidence  
- Prefer risk (`out_of_scope`) over practice (`reframeable`) over strength (`covered`)  
- Keep `suggested_share_pct` totaling ~100  
- Never advise claiming experience absent from the resume  

Note: the fallback builds its focus areas by looping `gaps.verdicts`. When the
crew never ran (no key), the gap report is empty, so the offline plan contains
the inferred seniority band and `_BAND_EMPHASIS` themes but **zero focus areas**.

---

## 2. Crew path (agent 5)

| Piece | Location |
|-------|----------|
| Role / backstory | `config/agents.yaml` → `interview_prep_advisor` |
| Task text | `config/tasks.yaml` → `build_prep_plan` (uses `{seniority}`) |
| Assembly | `crew.py` — MCP **off** (crew-level knowledge includes `interview_guidelines.md`) |
| Context tasks | `extract_profile`, `analyze_jd`, `analyze_gaps` |
| Output type | `InterviewPrepPlan` (Pydantic) |
| Kickoff input | `seniority` inferred from the JD (optional CLI `--seniority` override) |

**Why MCP off:** prep planning uses structured upstream outputs already in context; it does not re-read files.

**Knowledge:** [`knowledge/interview_guidelines.md`](../knowledge/interview_guidelines.md) — ranking rubric, seniority calibration, honesty bounds.

---

## 3. Fallback path (`build_fallback_plan`)

Open [`careercrew/prep.py`](../careercrew/prep.py).

| Step | Function / constant | What it does |
|------|---------------------|--------------|
| 1 | `seniority_band_from_label` + `_band_assessment` | Map UI/JD label → `SeniorityBand` (`early` / `mid` / `senior`); confidence from profile roles + JD seniority signal |
| 2 | Loop `gaps.verdicts` | Classify via `_verdict_class` |
| 3 | `_SHARE_BY_VERDICT` | Seed shares: out_of_scope 45, reframeable 30, covered 15 (then normalize to ~100) |
| 4 | Build `PrepFocus` rows | `area`, `priority`, `suggested_share_pct`, `why`, `evidence` (= requirement text) |
| 5 | `_BAND_EMPHASIS` | Add seniority-specific themes (fundamentals vs ownership vs system design) |
| 6 | Return `InterviewPrepPlan` | focus_areas, question_themes, strengths, risk_areas |

Called from `pipeline.run_analysis` after the crew path when `prep_plan is None`.

---

## 4. Guardrails

| Check | Function | Behavior |
|-------|----------|----------|
| Prep plan structure | `guardrails.validate_prep_plan(plan, gaps, requirements)` | Evidence must reference real gaps; priorities valid; shares ~100 |
| On failure | Pipeline | Adds **warnings** (does not abort the whole Analyze the way `validate_package` does) |

---

## 5. UI render

| Piece | Location |
|-------|----------|
| Tab | Gradio **Interview prep plan** |
| Renderer | `careercrew/ui_html.py` `_prep_html(plan)` |
| Shows | Seniority chips, focus cards (priority badge + % + why + “Grounded in” cite), themes, strengths, risk note |

Empty state: `_empty_card("Interview prep plan", ...)` until Analyze completes.

---

## 6. Downstream consumers

| Consumer | How prep plan is used |
|----------|------------------------|
| Mock interviewer | `interview.generate_questions(..., plan, ...)` biases questions toward risk areas / themes |
| Prep coach | `coach.build_context(..., prep_plan=...)` |
| Post-interview coach | Same context builder includes the plan |
| Analyze status line | Counts `len(result.prep_plan.focus_areas)` |

Serialized into Gradio `ctx_state` via `_serialize_result` after Analyze.
