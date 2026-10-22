# Code walkthrough

Per-file reference pages: what each module and function does, and why it is built
that way. Each page is self-contained and links back to the matching flow document.

Flow narratives (what happens after each button) live in
[`../CODE_PATH_*.md`](../CODE_PATH_ANALYZE.md). For a single continuous trace of
the Analyze path where every step shows its full code with the file and line
range (verified by `python tools/verify_doc_refs.py`), see
[`../ANALYZE_BUTTON_WALKTHROUGH.md`](../ANALYZE_BUTTON_WALKTHROUGH.md).

The other three buttons have the same treatment:

| Button | Walkthrough |
|--------|-------------|
| Analyze match | [`../ANALYZE_BUTTON_WALKTHROUGH.md`](../ANALYZE_BUTTON_WALKTHROUGH.md) |
| Apply updates & re-analyze | [`../REVISION_BUTTON_WALKTHROUGH.md`](../REVISION_BUTTON_WALKTHROUGH.md) |
| Start interview / Submit answer | [`../MOCK_INTERVIEW_WALKTHROUGH.md`](../MOCK_INTERVIEW_WALKTHROUGH.md) |
| Prep coach Send | [`../PREP_COACH_WALKTHROUGH.md`](../PREP_COACH_WALKTHROUGH.md) |
| Post-interview coach Send | [`../POST_INTERVIEW_COACH_WALKTHROUGH.md`](../POST_INTERVIEW_COACH_WALKTHROUGH.md) |

For the system picture first — context, layers, request lifecycle, agent
handoffs, review state machine, guardrails, and persistence, each as a diagram
with a short explanation — start with
[`../ARCHITECTURE_DIAGRAMS.md`](../ARCHITECTURE_DIAGRAMS.md).

## Reading order

The order below follows the data: an input arrives, the crew runs, the result is
validated and persisted, then it is used for practice.

| Area | Source | Reference page |
|------|--------|----------------|
| Page and event wiring | `app.py` → `callbacks_analyze.analyze` | [app.md](app.md) |
| Orchestrator | `careercrew/pipeline.py` → `run_analysis` | [pipeline.md](pipeline.md) |
| Five agents | `careercrew/crew.py`, `config/*.yaml` | [crew.md](crew.md), [config_agents_tasks.md](config_agents_tasks.md) |
| Tools and MCP | `document_tools.py`, `mcp_server/server.py`, `mcp_client.py` | [document_tools.md](document_tools.md), [mcp.md](mcp.md) |
| Contracts | `careercrew/models.py` | [models.md](models.md) |
| Guardrails | `careercrew/guardrails.py` | [guardrails.md](guardrails.md) |
| Prep advisor | `careercrew/prep.py` | [prep.md](prep.md) |
| HITL and storage | `review.py`, `session_store.py` | [review.md](review.md), [session_store.md](session_store.md) |
| Mock interview | `interview.py`, `audio.py`, `llm.py` | [interview.md](interview.md), [audio.md](audio.md), [llm.md](llm.md) |
| Coaches | `careercrew/coach.py` | [coach.md](coach.md) |
| CLI and settings | `main.py`, `config.py` | [main.md](main.md), [config.md](config.md) |

## Page list

- [app.md](app.md) — Gradio page layout and event wiring
- [pipeline.md](pipeline.md) — analysis orchestrator
- [crew.md](crew.md) — CrewAI assembly
- [config_agents_tasks.md](config_agents_tasks.md) — YAML roles and tasks
- [document_tools.md](document_tools.md) — resume and job-description readers
- [mcp.md](mcp.md) — MCP server and client
- [models.md](models.md) — Pydantic contracts
- [guardrails.md](guardrails.md) — input, output, and tool checks
- [prep.md](prep.md) — Interview Prep Advisor and fallback
- [review.md](review.md) — HITL state machine
- [session_store.md](session_store.md) — SQLite persistence
- [interview.md](interview.md) — mock interviewer logic
- [audio.md](audio.md) — speech-to-text and text-to-speech
- [llm.md](llm.md) — chat helper
- [coach.md](coach.md) — prep and post-interview coaches
- [main.md](main.md) — CLI
- [config.md](config.md) — settings and environment

## Scope

These pages cover the application modules and configuration. `ui_css.py` is
styling only; `tests/` and the `Dockerfile` are documented in
[`../engineering/testing-and-release.md`](../engineering/testing-and-release.md).
