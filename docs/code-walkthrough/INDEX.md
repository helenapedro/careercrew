# Code walkthrough index (professor live talk)

Open the **`.py` / `.yaml` on the left** and this guide (or the linked page) on the right.
Flow narrative (what happens after Analyze) lives in [`../CODE_PATH_*.md`](../CODE_PATH_ANALYZE.md).
For a single-click trace with verified line numbers, start with
[`../ANALYZE_BUTTON_WALKTHROUGH.md`](../ANALYZE_BUTTON_WALKTHROUGH.md).
This folder answers: **what does each function/block do and why?**

## How to use

1. Start from [`../SPEAKER_CHEATSHEET.md`](../SPEAKER_CHEATSHEET.md) for minute order  
2. Optional: open a [presentation notebook](../../notebooks/README.md) for big-screen explanations + offline demos  
3. Open the source file named below  
4. Follow the matching walkthrough page function-by-function  

## Talk order → files

| When | Open source | Walkthrough |
|------|-------------|-------------|
| Intro / honesty | `ARCHITECTURE.md`, `GLOSSARY.md`, `docs/CODE_TOUR.md` | (flow) CODE_PATH + ARCHITECTURE |
| Analyze click | `app.py` wires `callbacks_analyze.analyze` | [app.md](app.md) |
| Orchestrator | `careercrew/pipeline.py` → `run_analysis` | [pipeline.md](pipeline.md) |
| Five agents | `careercrew/crew.py`, `config/*.yaml` | [crew.md](crew.md), [config_agents_tasks.md](config_agents_tasks.md) |
| Tools + MCP | `document_tools.py`, `mcp_server/server.py`, `mcp_client.py` | [document_tools.md](document_tools.md), [mcp.md](mcp.md) |
| Contracts | `careercrew/models.py` | [models.md](models.md) |
| Guardrails | `careercrew/guardrails.py` | [guardrails.md](guardrails.md) |
| Prep advisor | `careercrew/prep.py` | [prep.md](prep.md) |
| HITL + DB | `review.py`, `session_store.py` | [review.md](review.md), [session_store.md](session_store.md) |
| Mock interview | `interview.py`, `audio.py`, `llm.py` | [interview.md](interview.md), [audio.md](audio.md), [llm.md](llm.md) |
| Coaches | `careercrew/coach.py` | [coach.md](coach.md) |
| CLI / settings | `main.py`, `config.py` | [main.md](main.md), [config.md](config.md) |

## Page list (all modules)

- [app.md](app.md) — Gradio page layout and event wiring
- [pipeline.md](pipeline.md) — analysis orchestrator
- [crew.md](crew.md) — CrewAI assembly
- [config_agents_tasks.md](config_agents_tasks.md) — YAML roles and tasks
- [document_tools.md](document_tools.md) — resume and job-description readers
- [mcp.md](mcp.md) — MCP server + client
- [models.md](models.md) — Pydantic contracts
- [guardrails.md](guardrails.md) — input/output/tool checks
- [prep.md](prep.md) — Interview Prep Advisor fallback
- [review.md](review.md) — HITL state machine
- [session_store.md](session_store.md) — SQLite persistence
- [interview.md](interview.md) — mock interviewer logic
- [audio.md](audio.md) — STT/TTS
- [llm.md](llm.md) — chat helper
- [coach.md](coach.md) — prep + post coaches
- [main.md](main.md) — CLI
- [config.md](config.md) — settings / env

## Scope note

`ui_css.py`, `tests/`, and Docker are out of scope for this pass (presentation-critical Python + YAML only).
