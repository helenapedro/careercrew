# CareerCrew — Request Lifecycle

**Status:** In progress
**Assessed commit:** `ee1f2fc6` (dev; same code on main)
**Scope of this trace:** CLI entry point (`main.py`), no `OPENAI_API_KEY` set, so the run takes the deterministic MCP fallback path. The six-agent crew path (with key) is described from code reading, not from a runtime observation.

## 1. Purpose

Describe the actual execution path for one representative user request: resume + job description + seniority band + one screening question, run through the CLI.

## 2. Scenario

- Entry point: `python main.py --resume samples/sample_resume.txt --jd samples/sample_jd.txt --seniority "5-10 years" --screening "Are you authorized to work in the US?"`
- Resume input: `samples/sample_resume.txt` (file upload path)
- Job-description input: `samples/sample_jd.txt` (file upload path)
- Expected output: screening-answers package + interview prep plan as JSON on stdout
- Environment: Python 3.12, no `OPENAI_API_KEY` (fallback mode), proxy env vars unset

## 3. Execution trace

| Step | Component | Function | Input | Output | Evidence |
|---|---|---|---|---|---|
| 1 | `main.py` | `main()` | CLI args | `AnalysisRequest` | `main.py:46-88`; runtime run 2026-10-16 |
| 2 | `main.py` | `check_upload` + `shutil.copyfile` | resume file | copy under `uploads/` | `main.py:60-62` |
| 3 | `main.py` | `redact_pii` | pasted JD text | redacted text | `main.py:76` (pasted text only) |
| 4 | `pipeline.run_analysis` | `guardrails.validate_request` | request | ok, else `ValueError` | `pipeline.py:326-336` |
| 5 | `pipeline` | `_prepare_resume_text` | request | resume text, else `ValueError("Could not read the resume")` | `pipeline.py:340-346`; file read via `read_resume` |
| 6 | `pipeline` | `_prepare_jd_text` | request | JD text, else `JobDescriptionError` | `pipeline.py:351-362` |
| 7 | `pipeline` | `settings.has_llm` check | env | `False` → crew skipped, warning recorded | `pipeline.py:369-381`; runtime warning observed |
| 8 | `pipeline` | `deterministic_package` | request, `MCPToolClient` | `ScreeningPrep` | `pipeline.py:146-186`; runtime JSON observed |
| 9 | `mcp_client` / `mcp_server` | `query_answer_bank` over stdio | screening question | answer dict (`found: true`) | runtime server log: `CallToolRequest` processed |
| 10 | `prep` | `build_fallback_plan` | empty profile/requirements/gaps + seniority | `InterviewPrepPlan` (generic) | `pipeline.py:414-422`; runtime JSON observed |
| 11 | `guardrails` | `validate_package` | package | ok, else `ValueError` (fail closed) | `pipeline.py:425-430` |
| 12 | `guardrails` | `validate_prep_plan` | plan | problem list → warnings | `pipeline.py:432-439` |
| 13 | `main.py` | `print` | `PipelineResult` | JSON on stdout | `main.py:90-96`; runtime output observed |

Observed runtime output (abridged): `ScreeningPrep` with one answer (`source: "answer_bank"`, `verified: true`, `do_not_claim: []`); `InterviewPrepPlan` with `seniority.band: "mid"` and generic `question_themes`, empty `focus_areas`/`strengths`/`risk_areas`; warnings: "No OPENAI_API_KEY set; running the deterministic MCP fallback only."

## 3b. Execution trace — Scenario B: UI full-crew run (runtime observed)

On 2026-10-16 Helena ran the Gradio UI (`python app.py`, `localhost:7860`) with an API key set: uploaded her real resume PDF (`Helena.Pedro-Resume.pdf`, 158.7 KB), pasted a job description, selected seniority "5-10 years". All 7 progress steps completed (Check inputs → Read resume → Understand role → Score match → Draft rewrites → Prep plan → Screening).

| Step | Observed behavior | Evidence |
|---|---|---|
| Input | PDF upload accepted; JD pasted; seniority band selected | PDF page 1: "Helena.Pedro-Resume.pdf 158.7 KB" |
| Profile Extractor | Structured profile: name, 6+ years summary, skills table, 3 roles with dates | "FROM YOUR RESUME" section |
| JD Analyzer | Requirements extracted: React, AI, AWS, Python, CI/CD Architecture + detailed items | "WHAT THE ROLE ASKS FOR" section |
| Gap Analyst | Match score 85/100; 16 covered, 3 reframeable, 0 out of scope; per-requirement evidence table | "Your match score" + requirement-by-requirement table |
| Feedback Writer | Suggested rewrites, each with "Based on:" citation | "SUGGESTED RESUME REWRITES" section |
| Talking points | Drafted with "(fact: ...)" citations | "TALKING POINTS" section |
| Screening prep | 1 verified answer from answer bank; 9 items flagged "still need your input" | "1 verified answer(s) · 9 item(s) still need your input" |
| DO NOT CLAIM | Unsupported items listed separately, not presented as experience | "DO NOT CLAIM" section |
| HITL | Decision prompt with Approve prep / Request changes / Reject buttons; "Nothing is finalized or submitted until you approve it." | "Your decision" section |
| Bundle | `pkg-1e731870` · 6 prep focus areas | "Your prep bundle is ready" banner |

Not exercised in this run: voice mock interview, coaching chats (tabs visible but not used).

## 4. External interactions

- **MCP server over stdio:** `mcp_server` launched as a subprocess by `MCPToolClient`; `ListToolsRequest` and `CallToolRequest` observed in the server log. Genuine MCP calls, not stubs.
- **LLM:** none (no key). With a key, `crew.py` would call the OpenAI API via CrewAI (code-traced, not runtime-observed here).
- **Filesystem:** reads `samples/`; copies uploads into `uploads/`; no SQLite writes on the CLI path (`main.py` does not import `session_store`).
- **Network:** none in fallback mode.

## 5. Error paths

| Condition | Behavior | Evidence |
|---|---|---|
| Missing/invalid inputs | `validate_request` fails → `ValueError` with messages | `pipeline.py:333-336` |
| Unreadable resume | `ValueError("Could not read the resume: ...")` | `pipeline.py:340-346` |
| Unreadable JD / URL pasted | `JobDescriptionError` (URLs rejected with guidance) | `pipeline.py:351-362`, `document_tools.py:137-139` |
| Crew fails (with key) | warning recorded, falls back to MCP path | `pipeline.py:374-379` |
| MCP fallback fails | empty `ScreeningPrep` + warning, never crashes | `pipeline.py:392-397` |
| Output guardrails fail | `ValueError`, fail closed | `pipeline.py:425-430` |
| User rejects in UI | review state machine → `REJECTED`, no approval | `review.py`, `app.py` buttons (verified in Phase 1) |

## 6. Findings

- **The fallback path is real, not a stub.** Screening answers came from genuine MCP `query_answer_bank` calls (observed `CallToolRequest` in the server log).
- **Without a key, analysis outputs are empty models.** `profile`, `requirements`, `gaps`, and `feedback` are empty Pydantic defaults; only screening answers and a generic prep plan are produced. The six agents never run.
- **PII redaction is input-method dependent.** `redact_pii` is applied to pasted text in `main.py`; file uploads go through `check_upload` + copy + `read_resume` with no redaction call in that path. Remaining uncertainty: whether `read_resume` redacts internally (not verified).
- **CLI does not persist.** No `session_store` usage on the `main.py` path; persistence (SQLite) is wired through the Gradio UI path only.
- **Crew path unverified at runtime.** Steps with `settings.has_llm=True` (`_run_crew`, `_parse_crew_outputs`) are code-traced only; a keyed run is needed for a runtime trace.

## 7. Open questions

- [x] Runtime-trace the six-agent crew path with an API key — done 2026-10-16 via the UI run above (Helena's key, her machine).
- [ ] Confirm whether `read_resume`/`read_job_description` redact PII for file uploads.
- [ ] Trace the Gradio UI path (`app.py`): HITL transitions, interview turns, chat persistence to SQLite.
- [ ] Trace the standalone MCP server path (`python -m mcp_server.server`).
- [ ] Measure wall-clock latency of the fallback path vs. the crew path.
