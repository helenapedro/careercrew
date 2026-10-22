# Walkthrough: `careercrew/prep.py`

**File purpose:** Interview Preparation Advisor logic — seniority-aware focus areas from gaps. Crew agent 5 produces the plan via YAML; this module owns the **deterministic fallback** (and optional LLM merge helpers).

**Flow:** [CODE_PATH_PREP.md](../CODE_PATH_PREP.md)

---

## Constants

| Symbol | Meaning |
|--------|---------|
| `_SHARE_BY_VERDICT` | Seed % before normalize: out_of_scope 45, reframeable 30, covered 15 |
| `_BAND_EMPHASIS` | Extra themes per `SeniorityBand` (fundamentals / ownership / system design) |

### `_verdict_class(verdict)`

Normalize string → `out_of_scope` / `reframeable` / `covered`.

### `_band_assessment(requested, profile, requirements)`

Map label → band; detect role count; confidence heuristic; build `SeniorityAssessment`.

---

## `build_fallback_plan(profile, requirements, gaps, requested_seniority)`

**What:**

1. Assess seniority  
2. For each gap verdict → `PrepFocus` with priority/share/why/evidence  
3. Sort high → low  
4. Normalize shares to ~100  
5. Themes = band emphasis + “Tell me about…” for the first five gaps  
6. Return `InterviewPrepPlan`  

**Why:** The prep tab keeps a seniority band and question themes without inventing experience. Note that focus areas come from `gaps.verdicts`, so a run with no gap report (no key) yields band + themes with an empty focus list.  
**Called by:** `pipeline.run_analysis` when the crew plan is missing (always, with no key).  
**Say this:** “Gaps drive prep time — out_of_scope first.”

---

## `build_prep_plan(..., llm=None)`

**What:** Always compute fallback; if `llm` provided, prompt → `merge_plan`; on failure return fallback.  
**Why:** Optional richer plan without depending on LLM for correctness.

### `_build_prompt` / `merge_plan`

Prompt asks for JSON matching `InterviewPrepPlan`; `extract_json` + validate; fill missing fields from fallback.

---

## How it connects

Crew path: agent `interview_prep_advisor` in YAML. Fallback path: this file. UI: `_prep_html`.
