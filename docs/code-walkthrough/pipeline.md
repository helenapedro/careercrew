# Walkthrough: `careercrew/pipeline.py`

**File purpose:** Orchestrates one Analyze run — guardrails, the five-agent crew
(or the gap-based fallback), typed models, output validation, then a `PipelineResult`.

**Flow doc:** [CODE_PATH_ANALYZE.md](../CODE_PATH_ANALYZE.md)

---

## Imports (why they exist)

| Import | Why |
|--------|-----|
| `json` / `re` | Parse LLM JSON (including fenced blocks); token matching for revision notes |
| `uuid` / `time` | Package ids and duration timing in the trace |
| `guardrails` | Input + output honesty checks |
| `document_tools` | Fail-fast resume/JD reads before the expensive crew |
| Models | Typed contracts for every stage |

---

## Types and constants

### `AnalysisRequest` (dataclass)

Normalized UI/CLI inputs: `package_id`, optional `resume_path`/`resume_text`,
optional `jd_path`/`jd_text`, `seniority`, and `revision_notes` (empty on the
first Analyze).

### `PipelineResult` (dataclass)

Everything the UI needs: `package`, `profile`, `requirements`, `gaps`,
`feedback`, `prep_plan`, `trace`, `request`, `warnings`, `used_fallback`.

### `CREW_STAGES`

Fixed list aligning CrewAI `tasks_output` order to keys: profile →
requirements → gaps → feedback → prep_plan.

---

## Functions (file order)

### `extract_json(raw)`

**What:** Strip → try fenced JSON → `json.loads` → if fail, slice first `{...}`
or `[...]` → else `None`.
**Why:** LLMs often wrap JSON in markdown fences.

### `_coerce_model(model_cls, data)`

**What:** If `data` is a `dict`, `model_validate`; on any error return `None`.
**Why:** Never crash the UI on a half-broken agent output — fall through to defaults.

### `_apply_revision_experience(profile, gaps, requirements, request)`

**What:** Folds the Request-changes notes into the profile as candidate-attested
experience, promotes matching `out_of_scope` verdicts to `covered`, and appends
matching JD tokens to `requirements.keywords`. Recomputes `coverage_score`.
**Why:** Offline runs skip the crew, so the attested experience has to reach the
gaps and prep plan through code.

### `_prepare_resume_text` / `_prepare_jd_text`

**What:** Prefer pasted text, else file path via `document_tools`; raise if neither.
**Why:** Fail fast before CrewAI burns tokens on a bad PDF.

### `_run_crew(request, trace, notify, on_task)`

**What:** Build `crew_inputs` (prefer paste over path when both concepts present),
`build_crew`, then `crew.kickoff(inputs=...)` — synchronous, already on a worker
thread. Times it and records `trace.add("crew.kickoff")`.
**Why:** Kickoff is blocking; `runner.py` already moved it off the UI thread.

### `_parse_crew_outputs(result, request, trace)`

**What:** Zip `tasks_output` with `CREW_STAGES`, `extract_json` each, coerce to
Pydantic. Returns a dict of the five models.
**Why:** Turns free-text agent output into typed objects the UI and guardrails can trust.

### `run_analysis(request, *, settings, progress, on_task)` — **main entry**

**What (four phases):**

1. `validate_request` — fail → raise `ValueError` + trace error
2. `_prepare_resume_text` / `_prepare_jd_text` — fail → clear error; also infers
   `seniority` from the JD when the request has none
3. If `settings.has_llm`: `_run_crew` + parse; on exception → warning, leave models `None`
   Else: warning “no API key”
4. Apply Request-changes notes, then `prep.build_fallback_plan(...)` when
   `prep_plan is None`
5. `validate_package` — **fail closed** (raise); `validate_prep_plan` — warnings only
6. Return `PipelineResult` (empty defaults for missing profile/gaps/etc.)

**Why:** One place owns honesty + graceful degradation.
**I/O:** Disk (reads), MCP, OpenAI, in-memory result (SQLite write happens later in review).

### `make_package_id()`

**What:** `pkg-` + 8 hex chars from UUID.
**Why:** Short id for the review dock without leaking a full UUID.

---

## How it connects

- **Called by:** `runner.stream_with_progress` (from the Analyze and
  Request-changes callbacks) and `main.py`
- **Calls:** `guardrails`, `document_tools`, `crew.build_crew`, `prep.build_fallback_plan`
