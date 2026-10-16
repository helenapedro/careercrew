# CareerCrew — Component Catalog

**Status:** In progress
**Assessed commit:** `ee1f2fc6` (dev; same code on main)

Each entry: responsibility, inputs → outputs, key dependencies, error behavior. Evidence is the source file; claims marked accordingly.

## Entrypoints

### `app.py` — Gradio web UI
- **Responsibility:** full interactive flow: upload/paste inputs, run analysis with live progress, HITL review buttons (Approve / Request changes / Reject), voice/text mock interview, prep and post-interview coaching chats, session tracker table.
- **Inputs → outputs:** user files/text in the browser → rendered prep bundle, transcript, chat replies.
- **Dependencies:** `pipeline.run_analysis`, `review.PackageReviewService`, `session_store`, `interview`, `audio`, `coach`, `guardrails`.
- **Errors:** `fail()` helper yields understandable messages (`main.py`-style statuses like "Resume rejected."); voice degrades to text with an explicit banner when no audio-capable key.

### `main.py` — CLI
- **Responsibility:** run one analysis from the terminal and print JSON.
- **Inputs → outputs:** `--resume`/`--resume-text`, `--jd`/`--jd-file`/pasted `--jd`, `--seniority`, `--screening` → `ScreeningPrep` + `InterviewPrepPlan` JSON on stdout.
- **Dependencies:** `pipeline.run_analysis`, `document_tools.check_upload`, `guardrails.redact_pii`.
- **Errors:** exits non-zero via raised `ValueError`/`JobDescriptionError`; no persistence (does not touch SQLite).

### `mcp_server/server.py` — MCP server (standalone)
- **Responsibility:** expose the shared tool logic as three MCP tools over stdio: `read_resume`, `read_job_description`, `query_answer_bank`.
- **Inputs → outputs:** MCP `CallToolRequest` → tool result payloads.
- **Dependencies:** `careercrew.document_tools` (single source of truth).
- **Errors:** tool errors surface as MCP error results; uploads-folder confinement enforced in `document_tools`.

## Orchestration

### `careercrew/pipeline.py` — `run_analysis`
- **Responsibility:** the one shared workflow: input guardrails → normalize inputs to text → run crew (if key) or deterministic MCP fallback → output guardrails → `PipelineResult`.
- **Inputs → outputs:** `AnalysisRequest` → `PipelineResult(package, profile, requirements, gaps, feedback, prep_plan, trace, warnings, used_fallback)`.
- **Dependencies:** `guardrails`, `crew` (`_run_crew`), `document_tools`, `mcp_client.MCPToolClient`, `prep.build_fallback_plan`, `models`.
- **Errors:** fail fast on bad inputs (`ValueError`/`JobDescriptionError`); crew failure degrades to fallback with a warning; output guardrails fail closed (`ValueError`); an `ExecutionTrace` records every step including errors. Never crashes the UI path.

### `careercrew/crew.py` — crew assembly
- **Responsibility:** turn `config/agents.yaml` + `config/tasks.yaml` into a running sequential CrewAI crew (`Process.sequential`, `allow_delegation: false`, `memory=True`), wiring MCP tools (stdio) and knowledge sources.
- **Inputs → outputs:** `AnalysisRequest` → raw crew result → parsed typed outputs (`_parse_crew_outputs`).
- **Dependencies:** `crewai`, `mcp_client.crewai_mcp_server`, `knowledge/*.md` via `StringKnowledgeSource`, `models`.
- **Errors:** crew exceptions are caught by `pipeline.run_analysis` and trigger the fallback path.

### `careercrew/config.py` — settings
- **Responsibility:** environment-driven settings (`Settings`): `upload_dir` (default `uploads`), `db_path` (default `careercrew.db`), `max_revisions` (default 2), `request_timeout_s`, `has_llm` (true when `OPENAI_API_KEY` set). Loads `.env` via `python-dotenv` (`override=False`, so real env vars win).
- **Errors:** invalid values fall back to defaults where safe.

## Tools and data

### `careercrew/document_tools.py` — tool implementations
- **Responsibility:** single source of truth for tools: `read_resume` / `read_resume_text` (PDF via pypdf, DOCX via python-docx, TXT), `read_job_description` (file or pasted text; **URLs rejected** with guidance), `query_answer_bank` (verified answers from `data/answer_bank.yaml`).
- **Dependencies:** `pypdf`, `python-docx`, `PyYAML`, uploads-folder confinement (`_safe_upload_path`).
- **Errors:** unsupported types/sizes → error; path traversal blocked; URLs → `JobDescriptionError` telling the user to upload/paste.

### `careercrew/mcp_client.py` — MCP client
- **Responsibility:** two faces of the same tools: `MCPToolClient` (real stdio client used by the deterministic fallback and tests) and `crewai_mcp_server()` (CrewAI `MCPServerStdio` config used by the agents).
- **Dependencies:** `mcp` SDK, subprocess launch of `mcp_server`.
- **Errors:** tool errors decoded via `_tool_error_text`; timeouts from settings.

### `data/answer_bank.yaml` — verified answer bank
- **Responsibility:** the ONLY facts the screening-prep writer may use. Entries carry `verified: true` only after candidate confirmation; unknown questions go to `do_not_claim`.
- **Errors:** missing entry → question flagged for user input, never invented.

### `knowledge/` — agent knowledge
- **Responsibility:** `resume_guidelines.md` (writing + honesty) and `interview_guidelines.md` (prep, interviewer, coaching conduct), loaded as `StringKnowledgeSource` for the agents.

## Validation

### `careercrew/guardrails.py`
- **Responsibility:** three layers:
  - *Input:* `validate_request` (exactly one resume/JD source, no injection patterns), `check_upload` (type/size), `redact_pii`.
  - *Output (per agent):* `validate_citations` (bullets cite real facts), `validate_package` (`source == "answer_bank"`), `validate_prep_plan` (focus areas cite real gaps), `validate_evaluation`, `validate_transcript_turn`, `validate_coaching_reply`.
  - *Tool:* uploads-folder confinement lives in `document_tools.py`.
- **Errors:** fail closed where it matters (package validation raises); prep-plan problems become warnings.

### `careercrew/review.py` — HITL state machine
- **Responsibility:** `PackageReviewService` enforces `DRAFT → PENDING_REVIEW → APPROVED / REJECTED`, with bounded `REVISE` back to a fresh `DRAFT` (`max_revisions`, default 2).
- **Inputs → outputs:** review actions → `ReviewDecision`, persisted state.
- **Errors:** invalid transitions raise `ReviewError`.

## Memory and persistence

### `careercrew/session_store.py` — SQLite
- **Responsibility:** stdlib-`sqlite3` persistence across restarts. Tables: `packages`, `decisions`, `interview_sessions`, `interview_turns`, `chat_messages`.
- **Dependencies:** none (standard library only).
- **Errors:** used by the UI path; the CLI path does not persist.

### `careercrew/models.py` — data contracts
- **Responsibility:** Pydantic contracts between agents. Key models: `CandidateProfile`, `JobRequirements`, `GapReport` (+`GapVerdict`), `FeedbackDraft` (+`RewrittenBullet`), `ScreeningPrep` (+`ScreeningAnswer`), `InterviewPrepPlan`, `InterviewQuestion`, `TranscriptTurn`, `AnswerEvaluation`, `MockInterviewSession`, `ChatMessage`, `ReviewStatus`/`ReviewAction`/`ReviewDecision`, `TrackerEntry`, `ExecutionTrace`/`TraceEvent`.
- **Errors:** invalid agent output fails Pydantic validation (parsed in `_parse_crew_outputs`).

## Preparation, interview, coaching

### `careercrew/prep.py`
- **Responsibility:** `build_prep_plan` (LLM path: prompt from profile/requirements/gaps + seniority band) and `build_fallback_plan` (deterministic, gap-based; used when the crew did not produce a plan).
- **Errors:** `merge_plan` reconciles raw LLM output with the fallback plan.

### `careercrew/interview.py` — mock interviewer
- **Responsibility:** `generate_questions` (grounded in JD/resume/gaps/plan), `evaluate_answer` (per-question `AnswerEvaluation`: score, what was wanted, strengths, improvements), `append_turn` (live transcript), `overall_evaluation` (session score + summary). Deterministic fallbacks run without a key.
- **Dependencies:** `llm.chat_completion`, `audio`, `guardrails.validate_interview_answer` / `validate_evaluation` / `validate_transcript_turn`.

### `careercrew/coach.py` — coaching chats
- **Responsibility:** `prep_coach_reply` (resume/preparation chat) and `post_coach_reply` (post-interview performance chat); both share `build_context` (pipeline outputs + persisted history) and fall back to a deterministic reply without a key.
- **Dependencies:** `guardrails.validate_coaching_reply` (no invented facts, no PII leakage).

### `careercrew/audio.py` — voice
- **Responsibility:** `transcribe` (whisper-1 STT), `speak` (tts-1 TTS), `audio_available()`, `cleanup`. Graceful: returns `None`/empty when no key, and the UI falls back to text.
- **Errors:** transcription/synthesis failures surface as errors to the UI, which keeps the text path usable.

### `careercrew/llm.py` — OpenAI helper
- **Responsibility:** thin wrapper: `available()`, `chat_completion(prompt, system, temperature=0.3)` used by interview/coach flows.
- **Errors:** no key → `available()` false → callers use deterministic fallbacks.

## Agent definitions

### `config/agents.yaml` + `config/tasks.yaml`
- **Responsibility:** the six agent roles/goals/backstories and their six tasks (roles and wiring only; tool/MCP/knowledge/output wiring lives in `crew.py`). Header comment: "nothing is auto-submitted anywhere."
- **Order:** Profile Extractor → JD Analyzer → Gap Analyst → Feedback Writer → Interview Prep Advisor → Screening Answer Prep Writer.
