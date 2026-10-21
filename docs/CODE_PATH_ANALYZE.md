# Code path: Analyze button

Live talk aid. Open the cited file/function while explaining. Nothing here
changes product behavior — it only documents it.

**Related:** [CODE_PATH_PREP.md](CODE_PATH_PREP.md) (Interview Prep Advisor detail) ·
[CODE_PATH_HITL.md](CODE_PATH_HITL.md) · [SPEAKER_CHEATSHEET.md](SPEAKER_CHEATSHEET.md)

---

## 1. Trigger

| Item | Detail |
|------|--------|
| UI control | Gradio button **Analyze match** (`run_btn`) in `app.py` `build_app()` |
| Handler | Generator `analyze(...)` in [`careercrew/callbacks_analyze.py`](../careercrew/callbacks_analyze.py) |
| Why a generator | Yields progress to the stage stepper before the long crew run finishes |

Wiring (conceptually): `run_btn.click(analyze, inputs=[...], outputs=[...])`.

---

## 2. End-to-end sequence

```mermaid
sequenceDiagram
  participant UI as app.py_analyze
  participant FS as uploads_folder
  participant PL as pipeline_run_analysis
  participant GR as guardrails
  participant DT as document_tools
  participant CR as crew_build_crew
  participant MCP as mcp_server_stdio
  participant LLM as OpenAI_API
  participant DB as session_store_SQLite
  participant REV as review_HITL

  UI->>UI: resolve resume/JD file or paste
  UI->>FS: copy upload into uploads/
  UI->>UI: make_package_id pkg-xxxxxxxx
  UI->>PL: ThreadPoolExecutor submit run_analysis
  PL->>GR: validate_request
  PL->>DT: prepare resume/JD text fail-fast
  alt has OPENAI_API_KEY
    PL->>CR: build_crew kickoff
    CR->>MCP: read_resume / read_job_description
    CR->>LLM: five agent completions
    PL->>PL: extract_json coerce models
  else no key or parse fail
    PL->>PL: deterministic build_fallback_plan from gaps
  end
  PL->>GR: validate_package validate_prep_plan
  PL-->>UI: PipelineResult
  UI->>REV: submit_for_review
  REV->>DB: save package PENDING_REVIEW
  UI->>UI: render Match + Prep, enable HITL buttons
```

---

## 3. Step table (open these while talking)

| # | What happens | File / symbol | I/O / API | Why |
|---|--------------|--------------|-----------|-----|
| 1 | Click Analyze → `analyze()` starts | `callbacks_analyze.py` `analyze` | UI event | Entry point for the whole analysis |
| 2 | Immediate yield: stage 1 “Checking…” | `analyze` / `_stages_html` | Gradio stream | Click never looks dead |
| 3 | Resolve resume | `_resolve_resume` | **Write** copy into `uploads/` if file; else pasted text | Agents only see confined uploads or paste |
| 4 | Resolve JD | `_resolve_upload(..., "job description")` | Same as resume | URLs are not fetched |
| 5 | Create request id | `pipeline.make_package_id` → `pkg-{8 hex}` | New id | Tracker / HITL key |
| 6 | Run pipeline off UI thread | `runner.stream_with_progress` | Worker thread | Gradio stays responsive; UI polls stages |
| 7 | Input guardrails | `guardrails.validate_request` | Fail → `ValueError` | Exactly one resume source + one JD source; injection/size checks |
| 8 | Fail-fast file/text read | `_prepare_resume_text` / `_prepare_jd_text` → `document_tools` | **Read** PDF/DOCX/TXT under uploads confinement | Bad files fail before the expensive crew |
| 9a | If `settings.has_llm` | `pipeline._run_crew` → `crew.build_crew` → `crew.kickoff` | CrewAI sequential + OpenAI HTTPS | Full five-agent path |
| 9b | MCP tools during crew | `mcp_client` + `mcp_server/server.py` | stdio subprocess to FastMCP | Real MCP (course requirement) |
| 9c | Parse task JSON → models | `extract_json`, `_coerce_model`, `_parse_crew_outputs` | In-memory | Typed contracts for tabs/guardrails |
| 10 | Fallback if no key / crew fail | `prep.build_fallback_plan` | Gap math | Demo works offline; never invents experience |
| 11 | Output guardrails | `validate_package`, `validate_prep_plan` | Fail closed on package; prep → warnings | Honesty story |
| 12 | Return `PipelineResult` | `pipeline.run_analysis` | In-memory | Bundle for UI |
| 13 | HITL submit | `review.submit_for_review` → `SessionStore.save_package` | **Write** SQLite `packages`; status `PENDING_REVIEW` | Survives a refresh |
| 14 | Render tabs + enable HITL | `_insight_html`, `_prep_html`; `ctx_state` | UI | Match / Prep plan; coaches/interview use `ctx_state` |

---

## 4. Five agents (sequential crew)

Config: [`config/agents.yaml`](../config/agents.yaml), [`config/tasks.yaml`](../config/tasks.yaml).  
Wiring: [`careercrew/crew.py`](../careercrew/crew.py) `build_crew()`.

| Order | Agent key | Task name | Typed output | MCP? | Knowledge |
|------:|-----------|-----------|--------------|------|-----------|
| 1 | `profile_extractor` | `extract_profile` | `CandidateProfile` | Yes (`read_resume`) | `resume_guidelines.md` |
| 2 | `jd_analyzer` | `analyze_jd` | `JobRequirements` | Yes (`read_job_description`) | resume guidelines |
| 3 | `gap_analyst` | `analyze_gaps` | `GapReport` | No | resume guidelines |
| 4 | `feedback_writer` | `write_feedback` | `FeedbackDraft` | No | resume guidelines |
| 5 | `interview_prep_advisor` | `build_prep_plan` | `InterviewPrepPlan` | No | + `interview_guidelines.md` |

**Context edges** (why order matters):

- Gap receives profile + JD tasks  
- Feedback receives gaps  
- Prep plan receives profile + JD + gaps  

**Process:** `Process.sequential`. Each task receives the previous task output. Crew memory is off so Analyze does not pay an extra model call per agent.

**Kickoff inputs** (`crew_inputs`): `resume_path`, `resume_text`, `jd_path`, `jd_text`, `seniority`, `revision_notes`.

---

## 5. MCP map

| MCP tool (server) | Shared implementation | Used by |
|-------------------|----------------------|---------|
| `read_resume_tool` | `document_tools.read_resume` | Profile Extractor |
| `read_job_description_tool` | `document_tools.read_job_description` | JD Analyzer (+ pipeline fail-fast) |

Server: [`mcp_server/server.py`](../mcp_server/server.py).  
Client / CrewAI config: [`careercrew/mcp_client.py`](../careercrew/mcp_client.py) (`MCPToolClient`, `crewai_mcp_server`).

**Tool guardrail:** paths confined to the uploads folder inside `document_tools` (no arbitrary disk reads).

---

## 6. Fallback decision tree

```
has OPENAI_API_KEY?
  ├─ yes → kickoff five-agent crew
  │         ├─ parse OK → use typed models
  │         └─ crew error → keep empty models, warn
  └─ no  → skip crew, warn: "No OPENAI_API_KEY…"

prep_plan is None?
  └─ yes → prep.build_fallback_plan(profile, requirements, gaps, seniority)

validate_package fails?
  └─ raise ValueError (fail closed; UI shows error)

validate_prep_plan problems?
  └─ warnings only (plan still shown)
```

Without a crew there is no profile, JD analysis, or gap report: the fallback
only builds the prep plan, and the match report stays empty. CareerCrew never
invents a resume fact or a work-authorization answer to fill the gap.

---

## 7. What Analyze writes / returns

| Artifact | Where | Contents |
|----------|-------|----------|
| Upload copies | `uploads/` | Resume/JD files (if uploaded) |
| `PipelineResult` | Memory → Gradio state | profile, requirements, gaps, feedback, prep_plan, package, trace, warnings |
| SQLite `packages` | `careercrew.db` | `package_id`, inputs JSON, package JSON, trace JSON, status=`pending_review`, revision_count |
| Match report tab | `_insight_html` | Coverage, verdicts, rewrites, talking points, do-not-claim |
| Interview prep plan tab | `_prep_html` | Seniority + focus areas (see [CODE_PATH_PREP.md](CODE_PATH_PREP.md)) |
| `ctx_state` | Gradio State | Serialized result for mock interview + coaches |

**Not done by Analyze:** mock interview audio, coach chats, approve/reject (those are later paths).

---

## 8. Models produced (contracts)

Defined in [`careercrew/models.py`](../careercrew/models.py):

- `CandidateProfile`, `JobRequirements`, `GapReport` / `GapVerdict`
- `FeedbackDraft` / `RewrittenBullet`
- `InterviewPrepPlan` / `PrepFocus` / `SeniorityAssessment`
- `ApplicationPackage` (the prep bundle the human reviews)
- `ExecutionTrace` / `TraceEvent`

---

## 9. UI stage mapping

`careercrew/runner.py` owns the stepper: a `Stage` enum (`CHECK_INPUTS`, `RESUME`,
`ROLE`, `MATCH`, `REWRITES`, `PREP`), `STAGES`, and the `AGENT_STAGE` /
`TASK_STAGE` maps from CrewAI names onto those steps. `on_task` advances the
stepper after each of the five tasks; the first yield marks stage 1 before the
crew starts.
