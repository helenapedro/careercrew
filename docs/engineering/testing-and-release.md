# Testing and Release

## 1. Test Plan

Run from the repository root:

```
python -m pytest tests/ -q
```

### Last recorded run

- **Date:** 2026-10-21; **branch:** `dev`; **Python:** 3.12.3
- **Result: 131 passed, 0 failed**

| Suite | Tests | Covers |
|---|---|---|
| `test_app_smoke.py` | 18 | Page builds, callbacks run offline, progress chrome, context round-trip |
| `test_audio.py` | 5 | Voice input/output paths (speech-to-text, text-to-speech) |
| `test_coach.py` | 24 | Preparation and post-interview coaching replies, analysis-anchored scope detection, typo tolerance |
| `test_document_tools.py` | 15 | Resume/JD reading, PII redaction, upload confinement |
| `test_guardrails.py` | 23 | Input, tool, and output guardrails, including citation validation |
| `test_interview.py` | 6 | Mock-interview question generation and answer evaluation |
| `test_llm.py` | 6 | Chat helper: retries, timeouts, models that reject `temperature` |
| `test_mcp_integration.py` | 3 | Real MCP round-trips for both document tools |
| `test_models.py` | 9 | Pydantic contracts for agent outputs and the prep bundle |
| `test_pipeline.py` | 8 | End-to-end analysis pipeline, including fallbacks |
| `test_prep.py` | 7 | Interview-prep plan generation |
| `test_review_workflow.py` | 7 | HITL state machine (`DRAFT` to `PENDING_REVIEW` to `APPROVED`/`REJECTED`, bounded `REVISE`) |

Environment note: in sandboxes that set proxy variables, `httpx` can fail at import while collecting `test_app_smoke.py` (it chokes on bracketed IPv6 entries in `no_proxy`). The suite is offline, so running with proxy variables unset avoids it; this is an environment quirk, not a repo failure.

## 2. Release Gates

From `careercrew-product-draft-v0.1.md`. All gates must pass before merging `dev` into `main`:

1. The automated test suite is green (`tests/`). — Last run 2026-10-21: 131 passed, 0 failed.
2. The demo path is verified end to end on `dev`: resume + JD in, approved package out; plus one mock-interview turn. — Verified 2026-10-21 via `tests/test_app_smoke.py` (analyze → approve → interview start/submit) and the coach gating test.
3. No secrets or credentials in the repo; API keys only via environment variables or platform Secrets. — Audited 2026-10-21: **passes**. `.env` is git-ignored and untracked; only `.env.example` (placeholder values) is committed, and no key-shaped string appears in tracked files.
4. `README.md` and `ARCHITECTURE.md` describe the released behavior. — **Confirmed** 2026-10-21: both documents were re-checked against the code, and their diagrams, line references, and limited-mode wording were corrected.
5. The merge PR is reviewed and approved. — Pending.
6. After merge: smoke-test `main` and record the release commit. — Pending.
