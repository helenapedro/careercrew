## 1. Test Plan

Run from the repository root:

```
python -m pytest tests/ -q
```

### Last recorded run

- **Date:** 2026-10-16; **branch:** `dev` at `61d7506`; **Python:** 3.12.3
- **Result: 112 passed, 0 failed**

| Suite | Tests | Covers |
|---|---|---|
| `test_answer_bank.py` | 6 | Verified answer-bank lookups used by the screening-prep writer |
| `test_app_smoke.py` | 9 | Application entry points start without errors |
| `test_audio.py` | 5 | Voice input/output paths (speech-to-text, text-to-speech) |
| `test_coach.py` | 6 | Preparation and post-interview coaching replies |
| `test_document_tools.py` | 13 | Resume/JD reading, upload confinement, answer-bank access |
| `test_guardrails.py` | 23 | Input, tool, and output guardrails, including citation validation |
| `test_interview.py` | 6 | Mock-interview question generation and answer evaluation |
| `test_mcp_integration.py` | 5 | CrewAI agents calling the MCP server tools |
| `test_models.py` | 13 | Pydantic contracts for agent outputs and preparation packages |
| `test_pipeline.py` | 10 | End-to-end analysis pipeline, including fallbacks |
| `test_prep.py` | 7 | Interview-prep plan generation |
| `test_review_workflow.py` | 9 | HITL state machine (`DRAFT` to `PENDING_REVIEW` to `APPROVED`/`REJECTED`, bounded `REVISE`) |

Environment note: in sandboxes that set proxy variables, `httpx` can fail at import while collecting `test_app_smoke.py` (it chokes on bracketed IPv6 entries in `no_proxy`). The suite is offline, so running with proxy variables unset avoids it; this is an environment quirk, not a repo failure.

## 2. Release Gates

From `careercrew-product-draft-v0.1.md`. All gates must pass before merging `dev` into `main`:

1. The automated test suite is green (`tests/`). — Last run 2026-10-16: 112 passed, 0 failed.
2. The demo path is verified end to end on `dev`: resume + JD in, approved package out; plus one mock-interview turn where voice is claimed. — Not yet run.
3. No secrets or credentials in the repo; API keys only via environment variables or platform Secrets. — `.env.example` documents the pattern; not yet audited.
4. `README.md` and `ARCHITECTURE.md` describe the released behavior. — Not yet confirmed.
5. The merge PR is reviewed and approved. — Pending.
6. After merge: smoke-test `main` and record the release commit. — Pending.
