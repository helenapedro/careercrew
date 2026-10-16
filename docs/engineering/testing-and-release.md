## 1. Test Plan (DRAFT)

Run from the repository root:

```
python -m pytest tests/ -q
```

| Suite | Covers |
|---|---|
| `test_answer_bank.py` | Verified answer-bank lookups used by the screening-prep writer |
| `test_app_smoke.py` | Application entry points start without errors |
| `test_audio.py` | Voice input/output paths (speech-to-text, text-to-speech) |
| `test_coach.py` | Preparation and post-interview coaching replies |
| `test_document_tools.py` | Resume/JD reading, upload confinement, answer-bank access |
| `test_guardrails.py` | Input, tool, and output guardrails, including citation validation |
| `test_interview.py` | Mock-interview question generation and answer evaluation |
| `test_mcp_integration.py` | CrewAI agents calling the MCP server tools |
| `test_models.py` | Pydantic contracts for agent outputs and preparation packages |
| `test_pipeline.py` | End-to-end analysis pipeline, including fallbacks |
| `test_prep.py` | Interview-prep plan generation |
| `test_review_workflow.py` | HITL state machine (`DRAFT` to `PENDING_REVIEW` to `APPROVED`/`REJECTED`, bounded `REVISE`) |

## 2. Release Gates (DRAFT)

From `careercrew-product-draft-v0.1.md`. All gates must pass before merging `dev` into `main`:

1. The automated test suite is green (`tests/`).
2. The demo path is verified end to end on `dev`: resume + JD in, approved package out; plus one mock-interview turn where voice is claimed.
3. No secrets or credentials in the repo; API keys only via environment variables or platform Secrets.
4. `README.md` and `ARCHITECTURE.md` describe the released behavior.
5. The merge PR is reviewed and approved.
6. After merge: smoke-test `main` and record the release commit.

**Note:** The suite descriptions and gate statuses in this document are draft until the verification pass proposed in `careercrew-product-draft-v0.1.md` is completed.
