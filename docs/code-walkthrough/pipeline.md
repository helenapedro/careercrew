# Walkthrough: `careercrew/pipeline.py`

**File purpose:** Orchestrates one Analyze run — guardrails, the five-agent crew (or the gap-based fallback), typed models, output validation, then a `PipelineResult`.

**Flow doc:** [CODE_PATH_ANALYZE.md](../CODE_PATH_ANALYZE.md)

---

## Imports (why they exist)

| Import | Why |
|--------|-----|
| `asyncio` | Run `crew.kickoff` in a thread via `asyncio.to_thread` so the sync pipeline can wait without blocking oddly |
| `json` / `re` | Parse LLM JSON, including fenced ` ```json ` blocks |
| `uuid` / `time` | Package ids and duration timing in the trace |
| `guardrails` | Input + output honesty checks |
| `document_tools` | Fail-fast resume/JD reads before the expensive crew |
| `MCPToolClient` | Deterministic screening fallback still uses **real** MCP |
| Models | Typed contracts for every stage |

---

## Types and constants

### `AnalysisRequest` (dataclass)

Normalized UI/CLI inputs: `package_id`, optional `resume_path`/`resume_text`, optional `jd_path`/`jd_text`, `screening_questions`, `seniority`.

**Say this:** “One object carries everything Analyze needs; exactly one resume source and one JD source are expected.”

### `PipelineResult` (dataclass)

Everything the UI needs: `package`, `profile`, `requirements`, `gaps`, `feedback`, `prep_plan`, `trace`, `warnings`, `used_fallback`.

### `CREW_STAGES`

Fixed list aligning CrewAI `tasks_output` order to keys: profile → requirements → gaps → feedback → prep_plan → package.

---

## Functions (file order)

### `extract_json(raw)`

**What:** Strip → try fenced JSON → `json.loads` → if fail, slice first `{...}` or `[...]` → else `None`.  
**Why:** LLMs often wrap JSON in markdown fences.  
**I/O:** None.  
**Say this:** “Bounded repair of messy model text into JSON.”

### `_as_list(value)`

**What:** Normalize `None` / list / comma-string / scalar into a list.  
**Why:** Agents sometimes return a string instead of a JSON array.

### `_coerce_model(model_cls, data)`

**What:** If `data` is a `dict`, `model_validate`; on any error return `None`.  
**Why:** Never crash the UI on a half-broken agent output — fall through to fallbacks.

### `deterministic_package(request, trace, mcp)`

**What:** For each screening question, call `mcp.query_answer_bank`; if `found`, append `ScreeningAnswer(source=answer_bank)`; else append to `do_not_claim`. Record each call on `trace`.  
**Why:** Without a working crew, screening answers must still be answer-bank-only (never invented).  
**I/O:** MCP stdio → answer bank.  
**Say this:** “Fallback still proves MCP; it does not invent work-auth facts.”

### `deterministic_screening_prep`

Alias of `deterministic_package` (legacy name).

### `_parse_package(data, package_id)`

**What:** Map screening-prep JSON dict into `ScreeningPrep` with per-answer repair; skip incomplete Q/A pairs.  
**Why:** Crew JSON is rarely perfect; bounded repair keeps honest answers.

### `_prepare_resume_text` / `_prepare_jd_text`

**What:** Prefer pasted text, else file path via `document_tools`; raise if neither.  
**Why:** Fail fast before CrewAI burns tokens on a bad PDF.

### `_run_crew(request, trace, notify, on_task)`

**What:** Build `crew_inputs` (prefer paste over path when both concepts present), `build_crew`, `asyncio.run(asyncio.to_thread(crew.kickoff, inputs=...))`, time and `trace.add("crew.kickoff")`.  
**Why:** Kickoff is blocking; thread keeps the process usable.  
**I/O:** OpenAI via CrewAI; MCP tools inside agents.  
**Say this:** “This is where the five agents actually run.”

### `_parse_crew_outputs(result, request, trace)`

**What:** Zip `tasks_output` with `CREW_STAGES`, `extract_json` each, coerce to Pydantic / `_parse_package`.  
**Why:** Turns free-text agent output into typed objects the UI and guardrails can trust.

### `run_analysis(request, *, settings, progress, on_task, allow_fallback)` — **main entry**

**What (branches):**

1. `validate_request` — fail → raise `ValueError` + trace error  
2. `_prepare_resume_text` / `_prepare_jd_text` — fail → clear error  
3. If `settings.has_llm`: `_run_crew` + parse; on exception → warning, leave models `None`  
4. Else: warning “no API key”  
5. If `package is None` and `allow_fallback`: `deterministic_package` via `MCPToolClient`  
6. Merge feedback `do_not_claim` into package  
7. If `prep_plan is None`: `prep.build_fallback_plan(...)`  
8. `validate_package` — **fail closed** (raise)  
9. `validate_prep_plan` — warnings only  
10. Return `PipelineResult` (empty defaults for missing profile/gaps/etc.)

**Why:** One place owns honesty + graceful degradation.  
**I/O:** Disk (reads), MCP, OpenAI, in-memory result (SQLite write happens later in review).  
**Say this:** “Guardrails in, crew or MCP fallback, guardrails out, then typed result.”

### `make_package_id()`

**What:** `pkg-` + 8 hex chars from UUID.  
**Why:** Short id for History / HITL without leaking a full UUID.

---

## How it connects

- **Called by:** `app.analyze`, `main.py`  
- **Calls:** `guardrails`, `document_tools`, `crew.build_crew`, `mcp_client`, `prep.build_fallback_plan`
