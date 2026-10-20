# Walkthrough: `app.py` (Gradio UI)

**File purpose:** Candidate-facing Gradio product. Wires Analyze, tabs, HITL, mock interview, and coaches. Business logic lives in `careercrew/*`; this file is orchestration + HTML.

**Flow docs:** [CODE_PATH_ANALYZE](../CODE_PATH_ANALYZE.md) · [HITL](../CODE_PATH_HITL.md) · [MOCK](../CODE_PATH_MOCK_INTERVIEW.md) · [COACH](../CODE_PATH_COACH.md)

CSS lives in `careercrew/ui_css.py` (not agent logic — skip in the talk unless asked).

---

## Module setup

| Symbol | Role |
|--------|------|
| `_SETTINGS` / `_STORE` / `_REVIEW` | Settings, SQLite store, HITL service |
| `STAGES` / `_AGENT_STAGE` / `_TASK_STAGE` | Progress stepper mapping for Analyze |
| `CUSTOM_CSS` | Imported from `ui_css` |

---

## UI chrome (group when talking)

`_esc`, `_alert_html`, `_mode_banner`, `_topbar`, `_hero`, `_stages_html`, `_empty_card`, `_trace_markdown` — HTML helpers for branding, errors, progress, Advanced trace.

**HTML tab renderers (short note each):**

| Function | Tab content |
|----------|-------------|
| `_insight_html` | Match report (coverage, verdicts, rewrites, talking points, do-not-claim) |
| `_package_html` | Screening answers + needs-your-input |
| `_prep_html` | Interview prep plan cards |
| `_question_html` / `_evaluation_html` / `_overall_html` | Mock interview panels |
| `_audio_status` | Banner if TTS/STT unavailable |

**Say this:** “These build HTML strings for Gradio; the intelligence is in the pipeline/interview/coach modules.”

---

## Upload resolution

### `_resolve_resume` / `_resolve_upload(upload, pasted, kind)`

**What:** If Gradio file present → copy into `uploads/` with basename only → return `(filename, None)`. Else if paste → return `(None, text)`. Else `(None, None)`.  
**Why:** MCP tools only accept bare filenames under uploads.  
**I/O:** Disk write to uploads.  
**Say this:** “We never pass absolute paths to agents.”

---

## Analyze (core)

### `analyze(...)` — generator

**What:**

1. Yield immediate “Starting…” progress  
2. Resolve resume + JD; fail early with `_alert_html`  
3. Parse screening lines; build `AnalysisRequest` + `make_package_id`  
4. Submit `run_analysis` on `ThreadPoolExecutor`; poll `stages` via `progress` / `on_task` and yield stepper updates  
5. On success: `_REVIEW.submit_for_review(...)` (SQLite PENDING_REVIEW)  
6. Yield filled tabs: insight, prep, package, JSON, enable HITL buttons, `ctx_state` = `_serialize_result`  

**Why generator:** Live stage UI without freezing Gradio.  
**I/O:** uploads, OpenAI/MCP via pipeline, SQLite via review.  
**Say this:** “Click Analyze → this generator → pipeline on a worker thread → tabs fill.”

### `_serialize_result` / `_load_context` / `_context_models`

Pack/unpack Analyze results for interview + coach tabs (JSON in Gradio State).

### `_empty_outputs`

Reset tuple for clear/error paths.

---

## HITL handlers

| Function | Action |
|----------|--------|
| `_load_package` / `_current_status` | State → ScreeningPrep; SQLite status + revisions |
| `approve` | `ReviewAction.APPROVE` → message with prep bundle id + next-tab hint |
| `reject` | `REJECT` |
| `request_revision` | `REVISE` (notes required) → re-runs `run_analysis` with saved inputs + `revision_notes`, refreshes all result tabs |
| `_tracker_rows` | History dataframe from `list_packages` |

**Say this:** “Approve only changes SQLite status — nothing is submitted to an employer.”

---

## Mock interview handlers

| Function | What |
|----------|------|
| `interview_start` | Require context → `generate_questions` → `MockInterviewSession` → `_ask_question(0)` |
| `_ask_question` | TTS `audio.speak` → append interviewer turn → `save_interview` → render |
| `interview_submit` | STT or text → `validate_interview_answer` → `evaluate_answer` → candidate turn → next Q or `overall_evaluation` |
| `_turns_to_messages` | Transcript → Chatbot messages |
| `_load_interview` | Parse `iv_state` JSON |

---

## Coach handlers

| Function | What |
|----------|------|
| `_render_prep_chat` | `build_context` (no interview) → `prep_coach_reply` → persist `channel=prep` |
| `_render_post_chat` | Context + `include_interview` from `iv_state` → `post_coach_reply` → `channel=post` |

---

## `build_app` / `theme` / `main`

**What:** Construct Gradio Blocks (inputs, tabs, HITL dock), wire `.click` handlers to the functions above, launch on `0.0.0.0:_SETTINGS.app_port` with theme + CSS.  

**Say this:** “build_app is layout and wiring only.”

---

## How it connects

Calls `pipeline`, `review`, `session_store`, `interview`, `audio`, `coach`, `llm`, `guardrails`.
