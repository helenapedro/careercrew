# CareerCrew: Architecture Gaps

**Status:** In progress
**Assessed commit:** `ee1f2fc6` (dev; same code on main)

Comparison between intended behavior (README, `ARCHITECTURE.md`, `docs/engineering/`) and the implementation as verified in Phase 1–2. Statuses: **Verified** (code + test/runtime evidence), **Partial** (implemented but not fully verified), **Not implemented**, **Unknown**.

| Capability | Intended behavior | Evidence from implementation | Status |
|---|---|---|---|
| Resume ingestion (PDF/DOCX/TXT, pasted text) | Accept resume via upload or paste | `document_tools.read_resume`, `guardrails.check_upload`; `tests/test_document_tools.py` (13 tests) | Verified |
| JD ingestion | Accept JD via upload or paste; URLs rejected with guidance | `document_tools.read_job_description`, `_looks_like_url`; runtime CLI trace | Verified |
| Six-agent sequential pipeline | Six agents run in fixed order, no delegation | `config/agents.yaml`, `crew.py` (`Process.sequential`); **runtime:** 7/7 progress steps completed in Helena's UI run 2026-10-16 | Verified (runtime) |
| Coverage scoring and gap verdicts | Honest 0–100 scoring, covered/reframeable/out-of-scope | `gap_analyst` task config; **runtime:** score 85/100, 16 covered / 3 reframeable / 0 out of scope | Verified (runtime) |
| Cited resume feedback | Every bullet cites a profile fact | `validate_citations`; **runtime:** rewrites shown with "Based on:" citations, talking points with "(fact:)" | Verified (runtime) |
| Seniority-aware prep plan | Plan calibrated to 2–3 / 5–10 / 10+ years | `prep.build_prep_plan`; **runtime:** 6 prep focus areas in bundle `pkg-1e731870` | Verified (runtime) |
| Screening answers from answer bank | Answers only from verified entries; unknowns → `do_not_claim` | Runtime CLI trace: real MCP `query_answer_bank` call, `source: "answer_bank"` | Verified (runtime) |
| HITL review in UI | Approve / Request changes / Reject wired to state machine | `app.py` buttons → `review.PackageReviewService`; **runtime:** decision prompt + 3 buttons rendered, "Nothing is finalized or submitted until you approve it." | Verified (runtime) |
| Bounded revisions | Max 2 revisions (configurable) | `config.py:89` (`CAREERCREW_MAX_REVISIONS`, default 2) | Verified |
| Voice mock interview | Voice Q&A with transcript and evaluation; text fallback | `interview.py`, `audio.py`; fallback verified in `app.py`; voice path itself needs a key | Partial |
| Coaching chats | Prep + post-interview chats with full memory | `coach.py`; `tests/test_coach.py` (6 tests); runtime chat not traced | Partial |
| SQLite persistence | Packages, decisions, sessions, turns, chats survive restarts | 5 tables in `session_store.py`; UI path only (CLI does not persist) | Partial |
| MCP integration | Tools exposed/consumed over stdio | Runtime trace: `ListToolsRequest` + `CallToolRequest` observed; `tests/test_mcp_integration.py` | Verified (runtime) |
| Deterministic fallback | Full app behavior without API key, banner in UI | Runtime CLI trace; `pipeline.py` fallback branch; README documents it | Verified (runtime) |
| PII redaction | Personal data redacted before LLM calls | `redact_pii` on pasted text in `main.py`; file-upload path not verified | Partial |
| Nothing is submitted | CareerCrew never applies on the user's behalf | Design + `agents.yaml` header comment; no submission code paths found | Verified |
| Input guardrails | Type/size/source validation, injection patterns | `guardrails.validate_request`, `check_upload`; 23 guardrail tests | Verified |
| Output guardrails | Citations, package, prep-plan validation; fail closed | `validate_citations`/`validate_package`/`validate_prep_plan`; fail-closed raise in pipeline | Verified |
| Deployment (HF Spaces) | Dockerfile → Spaces (Docker SDK) | `Dockerfile` exists (py3.12-slim, :7860, non-root, /data); not deployed | Partial |
| Deployment target decision | Heroku under evaluation | Note in `ARCHITECTURE.md` §5 (helena/work) | Unknown (pending decision) |

## Unknowns (need evidence)

- SQLite failure modes (locked/corrupt DB behavior).
- CrewAI retry/timeout configuration, if any.
- MCP subprocess lifecycle: restart behavior if it dies mid-run.
- `_coerce_model` on partially valid agent output (code-traced as raise → fallback; unconfirmed).
- Wall-clock latency and cost per analysis (no measurements yet).
- Accessibility of the Gradio UI (no audit).

## Notes

- "Verified (code)" means the implementation was read and its tests pass; "Verified (runtime)" means it was observed executing. The distinction is deliberate: the six-agent LLM path is code-verified only, because no API key was available for a runtime trace.
- Gaps marked Partial/Unknown are candidates for Phase 3 (correctness and risk assessment), not for fixing during Phase 2.
