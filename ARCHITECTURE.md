# CareerCrew architecture

> This file has one job: explain how the system is put together.
>
> - Product scope and users: `docs/engineering/product-overview.md`
> - Requirements and evidence: `docs/engineering/functional-nonfunctional-requirements.md`
> - Setup and run instructions: `docs/engineering/setup.md`
> - Tests and release gates: `docs/engineering/testing-and-release.md`
> - Agent and task details: `docs/engineering/agents-and-workflows.md`
> - Use cases and user stories: `docs/engineering/use-cases-and-user-stories.md`
> - Diagrams with short explanations: `docs/ARCHITECTURE_DIAGRAMS.md`


## 1. System overview

A user provides a resume (file or pasted text) and a job description (file or
pasted text). Seniority is inferred from the JD. Five agents run in a fixed
sequence and produce cited feedback plus a seniority-aware interview
preparation plan. On top of that, a voice
**mock interviewer** runs a practice interview with a live transcript and
per-question feedback, and two **coaching chats** answer follow-up questions.

Every claim in the output must trace to a resume fact; the system says
"do not claim" rather than invent facts.
**Nothing is submitted anywhere** - CareerCrew prepares and practices; the
candidate applies.

```mermaid
flowchart TD
    S1["1 · Input<br/>resume + JD<br/>(seniority inferred from JD)"]
    S2["2 · Entrypoints<br/>app.py — Gradio UI<br/>main.py — CLI"]
    S3["3 · Input guardrails<br/>validate_request · check_upload · redact_pii"]
    S4["4 · Pipeline<br/>normalize to text · build crew<br/>kickoff · parse · fallback"]
    S5["5 · Analysis crew — five sequential agents<br/>1 Profile Extractor → 2 JD Analyzer → 3 Gap Analyst<br/>→ 4 Feedback Writer → 5 Interview Prep Advisor"]
    S6["6 · Output guardrails<br/>validate_citations · validate_package · validate_prep_plan"]
    S7["7 · HITL review<br/>DRAFT → PENDING_REVIEW → APPROVED / REJECTED"]
    S8["8 · Prep bundle<br/>bullets · talking points · prep plan"]
    S9["9 · Practice and coaching<br/>voice/text mock interview<br/>prep coach · post-interview coach"]

    S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S8 --> S9

    S5 <--> MCP["MCP server — stdio<br/>read_resume_tool · read_job_description_tool"]
    S4 -.-> K["knowledge/<br/>resume_guidelines.md<br/>interview_guidelines.md"]
    S7 -.-> DB[("SQLite session store<br/>bundles · decisions · sessions · turns · chats")]
    S9 -.-> DB
```

## 2. Component legend

| Node | Component | Responsibility |
|---|---|---|
| `S2` | `app.py`, `main.py` | Gradio web interface and CLI entrypoints. |
| `S3` | `careercrew/guardrails.py` | Pre-LLM checks: exactly one resume/JD source, upload type and size, injection patterns, PII redaction. |
| `S4` | `careercrew/pipeline.py` | Normalizes inputs to text, kicks off the crew, parses/validates outputs, and runs deterministic fallbacks. |
| `S5` | `careercrew/crew.py` | Turns `config/*.yaml` into a running sequential crew with MCP tools and knowledge sources. |
| `1`–`5` | `config/agents.yaml`, `config/tasks.yaml` | The five sequential agents and their tasks (details in `docs/engineering/agents-and-workflows.md`). |
| `MCP` | `mcp_server/server.py` | Exposes the shared tool logic over stdio as two MCP tools. |
| `S6` | `careercrew/guardrails.py` | Per-agent output checks: citations trace to real facts, and prep-plan focus areas cite real gaps. |
| `S7` | `careercrew/review.py` | Human-in-the-loop state machine (see §3). |
| `S8` | `careercrew/models.py` | Approved prep bundle: `ApplicationPackage` carries the bundle id, role, company, summary, and the `do_not_claim` list. The detail lives beside it in `PipelineResult` (profile, requirements, gaps, feedback, prep plan). Nothing is submitted. |
| `S9a` | `careercrew/interview.py`, `careercrew/audio.py` | Voice mock interviewer: question generation, `whisper-1` STT / `tts-1` TTS, live transcript, per-answer evaluation. |
| `S9b` | `careercrew/coach.py` | `prep_coach_reply` (resume and preparation chat) and `post_coach_reply` (post-interview performance chat with transcript and scores in context). |
| `DB` | `careercrew/session_store.py` | SQLite persistence: bundles, review decisions, interview sessions and turns, and both chat channels. The UI reads back the current package and the latest interview; chat history is write-only. |
| `K` | `knowledge/` | `resume_guidelines.md` (writing + honesty) and `interview_guidelines.md` (prep, interviewer, and coaching conduct). |

`careercrew/document_tools.py` is not a separate node: it is the shared implementation
behind both the MCP server and the deterministic fallback.

## 3. HITL review loop

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> PENDING_REVIEW : submit for review
    PENDING_REVIEW --> APPROVED : approve
    PENDING_REVIEW --> REJECTED : reject
    PENDING_REVIEW --> DRAFT : request revision<br/>(bounded: max 2)
    APPROVED --> [*]
    REJECTED --> [*]
```

`careercrew/review.py` enforces the transitions. A requested revision returns
to a fresh `DRAFT`; the revision count is bounded (`CAREERCREW_MAX_REVISIONS`,
default 2). In the UI the three transitions are the **Approve prep bundle**,
**Request changes**, and **Reject** buttons. Approval is reframed around the
prep bundle: nothing is ever submitted to an employer.

Approval also **gates downstream use**: the mock interview and both coaching
chats call `_is_approved()` (`careercrew/callbacks_interview.py`), which reads the
persisted `packages.status` and refuses to run unless it is `APPROVED`. The
analysis results stay readable while pending, because the candidate needs them in
order to decide.

## 4. Key design decisions

1. **Sequential crew, not hierarchical.** The analysis pipeline is linear
   (extract → analyze → compare → write → plan). There is no delegation
   decision to make, so a manager agent would add latency and cost
   for no benefit.
2. **MCP over stdio, in-process.** One tool implementation
   (`document_tools.py`) serves the agents, the deterministic fallback, and
   the tests. No second service to deploy or keep alive.
3. **SQLite for memory.** Standard library only, survives restarts, no
   infrastructure. Each agent already receives the previous task's output,
   so the crew does not also store a separate short-term memory.
4. **Limited mode without a key.** The app runs without `OPENAI_API_KEY`, but
   the crew is skipped: profile, requirements, and gaps stay empty, so the match
   report is empty and the prep plan carries only the seniority band and themes
   (no focus areas — there are no gaps to derive them from). The UI banner says so.
5. **Evidence grounding.** Every factual claim traces to a supplied resume
   fact. Unsupported claims go to `do_not_claim` instead of being invented.

## 5. Deployment

One container image, one port. Any Docker host works: a small cloud VM or a
university machine.

```mermaid
flowchart LR
    USER["Candidate<br/>(browser)"] --> APP["app.py — Gradio UI<br/>listens on 0.0.0.0:7860"]
    subgraph HOST["Docker host"]
        APP <--> MCPD["mcp_server<br/>stdio, in-process<br/>no second service"]
        APP --> DBD[("SQLite — /data<br/>careercrew.db + uploads")]
    end
    SEC[".env on the host<br/>OPENAI_API_KEY"] -.-> APP
```

`Dockerfile` (python:3.12-slim): installs `requirements.txt`, copies the app
and `samples/`, runs as non-root `appuser` with a writable `/data` directory,
healthchecks the Gradio root, `CMD ["python", "app.py"]`. The OpenAI key stays
in `.env` on the host, never in the repo.

## 6. Architecture verification checklist

Verified 2026-10-21 against `dev`.

- [x] Confirm the actual UI entry points and supported input methods.
- [x] Confirm the exact agent/task sequence and data contracts.
- [x] Confirm whether MCP tools and deterministic fallbacks are both implemented.
- [x] Confirm how output validation, retries, and package completeness are enforced.
- [x] Confirm whether human approval/revision/rejection exists in the UI or is only a proposed interaction.
- [x] Confirm which workflows use SQLite or other persistence and what is stored.
- [x] Confirm the actual mock-interview, voice/text, and coaching paths.
- [x] Update the diagram to distinguish in-process modules from external services.

## 7. Reading order for learning the codebase

1. `config/agents.yaml` + `config/tasks.yaml` (what the crew is)
2. `careercrew/models.py` (the contracts between agents)
3. `careercrew/crew.py` (how YAML becomes a running crew with MCP + knowledge)
4. `careercrew/document_tools.py` (tools + guardrails)
5. `careercrew/pipeline.py` (orchestration, parsing, fallback, validation)
6. `careercrew/prep.py`, `careercrew/interview.py`, `careercrew/coach.py`
   (prep plan, mock interviewer, coaching chats)
7. `careercrew/audio.py` + `careercrew/llm.py` (audio and LLM helpers)
8. `careercrew/review.py` + `careercrew/session_store.py` (HITL + persistence)
9. `mcp_server/server.py` (the same tools over MCP)
10. `app.py`, then `main.py` (entrypoints)
