# Speaker cheatsheet — technical presentation

Use this live. Open the file named in each minute block; scroll to the symbol.

**Deep docs:** [CODE_PATH_ANALYZE.md](CODE_PATH_ANALYZE.md) · [CODE_PATH_PREP.md](CODE_PATH_PREP.md) ·
[CODE_PATH_HITL.md](CODE_PATH_HITL.md) · [CODE_PATH_MOCK_INTERVIEW.md](CODE_PATH_MOCK_INTERVIEW.md) ·
[CODE_PATH_COACH.md](CODE_PATH_COACH.md) · [ARCHITECTURE.md](../ARCHITECTURE.md)

---

## Minute 0–3 — What CareerCrew is

| Say | Open |
|-----|------|
| Six agents, no auto-submit, prep + practice | `README.md` top + `ARCHITECTURE.md` §1 diagram |
| Honesty: citations + answer bank + do-not-claim | `data/answer_bank.yaml` (one verified entry) |

---

## Minute 3–12 — Analyze button (core)

| Say | Open |
|-----|------|
| Click → generator | `app.py` → `analyze` |
| Uploads confinement | `app.py` → `_resolve_upload` / `_resolve_resume` |
| Orchestrator | `careercrew/pipeline.py` → `run_analysis` |
| Input guardrails | `careercrew/guardrails.py` → `validate_request` |
| Crew assembly | `careercrew/crew.py` → `build_crew` |
| Agent/task YAML | `config/agents.yaml` + `config/tasks.yaml` |
| MCP tools | `mcp_server/server.py` (three tools) |
| Shared tool logic | `careercrew/document_tools.py` |
| Fallback | `pipeline.py` → `deterministic_package` |
| Persist for HITL | `careercrew/review.py` → `submit_for_review` |

Optional live demo: run Analyze on `samples/` while the stepper moves.

---

## Minute 12–15 — Interview Prep Advisor

| Say | Open |
|-----|------|
| Agent 5 in the sequence | `config/tasks.yaml` → `build_prep_plan` |
| Fallback without LLM | `careercrew/prep.py` → `build_fallback_plan` |
| UI tab | Gradio **Interview prep plan** / `_prep_html` |
| Detail doc | `docs/CODE_PATH_PREP.md` |

---

## Minute 15–18 — HITL + where `pkg-…` lives

| Say | Open |
|-----|------|
| State machine | `careercrew/review.py` (`_ALLOWED`) |
| Approve / revise / reject | `app.py` → `approve` / `request_revision` / `reject` |
| History = package id | Gradio **History** tab; SQLite `packages` in `session_store.py` |
| Content of the bundle | **Screening answers** tab |

---

## Minute 18–25 — Virtual mock interviewer

| Say | Open |
|-----|------|
| Start | `app.py` → `interview_start` |
| Questions | `careercrew/interview.py` → `generate_questions` |
| TTS / STT | `careercrew/audio.py` → `speak` / `transcribe` |
| Evaluate + overall | `evaluate_answer` / `overall_evaluation` |
| Transcript sync | `_turns_to_messages` + Chatbot |
| Detail doc | `docs/CODE_PATH_MOCK_INTERVIEW.md` |

Demo tip: text-only works without a mic if the key is missing (fallback).

---

## Minute 25–30 — Coaches

| Say | Open |
|-----|------|
| Shared context builder | `careercrew/coach.py` → `build_context` |
| Prep vs post | `prep_coach_reply` vs `post_coach_reply` (`include_interview`) |
| Guardrails | `validate_coaching_reply` |
| Persistence | `chat_messages` in `session_store.py` |
| Detail doc | `docs/CODE_PATH_COACH.md` |

---

## If asked “why sequential, not hierarchical?”

Open `ARCHITECTURE.md` §4 / `crew.py` docstring: extract → JD → gap → write → prep → screening is linear; a manager adds cost without a delegation decision.

---

## If asked “what if no API key?”

Point at `pipeline.run_analysis` branches + `deterministic_package` + `build_fallback_plan` + audio/coach fallbacks. Screening answers still come only from the answer bank via MCP.
