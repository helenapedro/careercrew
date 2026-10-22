# CareerCrew

Multi-agent resume, interview, and job-application coach built with CrewAI and
MCP (CS529 Project Work 2). Five specialized agents turn a resume and a job
description into honest, cited guidance: coverage scoring, gap analysis, tailored
bullet rewrites, and a seniority-aware **interview preparation plan**.

On top of the analysis, CareerCrew adds a **voice virtual mock interviewer**
(spoken questions, live synchronized transcript, per-question feedback) and two
**full-memory coaching chats** — a resume/preparation coach and a
post-interview performance coach that remembers the whole session.

**Nothing is submitted anywhere.** CareerCrew prepares and practices; the
candidate applies themselves.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # then put your OPENAI_API_KEY in .env
```

Run the pipeline on the samples (fictional test data):

```bash
python main.py --resume samples/sample_resume.txt --jd samples/sample_jd.txt
```

Pasted text and an uploaded JD file also work:

```bash
python main.py --resume-text "JANE DOE. Python, FastAPI, AWS." --jd "We need a Python engineer."
python main.py --resume samples/sample_resume.txt --jd-file samples/sample_jd.txt
```

Run the web UI:

```bash
python app.py
```

Run the MCP server standalone (for a manual smoke test):

```bash
python -m mcp_server.server
```

The app runs without an `OPENAI_API_KEY`, in **limited mode**: the page, the review
dock, and the persistence all work, but the crew is skipped, so the match report
stays empty and the prep plan has seniority band + themes only (no focus areas,
because there are no gap verdicts to derive them from). The UI banner says so.
Add a key for the full crew and the voice interview.

## Input rules

- **Resume** — upload a `.pdf`, `.docx`, or `.txt` file **or** paste the resume
  text. Provide exactly one.
- **Job description** — upload a `.pdf`, `.docx`, or `.txt` file **or** paste the
  text. Provide exactly one. Job-posting **URLs are not read directly** (job
  boards block automated access); the app tells you to upload the file or paste
  the text instead. Target experience / seniority for the prep plan is
  **inferred from the JD** (years of experience and title signals).

## Features

- **Match report** — coverage score, per-requirement verdicts (Covered /
  Reframeable / Out of Scope), cited resume rewrites, and talking points.
- **Interview prep plan** — where to spend the most preparation time, derived
  from the gaps and the target seniority band.
- **Voice mock interview** — the interviewer asks questions from the application,
  the candidate answers by voice or text, and each answer gets real-time feedback
  (what the interviewer wanted, what to improve). Speech-to-text and
  text-to-speech use the OpenAI audio API; without a key it degrades to a
  text-only interview.
- **Prep coach chat** — iterate on resume improvements and preparation.
- **Post-interview coach chat** — ask anything about performance; the coach has
  the resume, JD, gap report, prep plan, the full transcript, and the per-answer
  evaluations (each with its own 0-100 score).
- **Guardrails everywhere** — input validation, PII redaction, grounded prep
  advice, bounded scoring, safe coaching replies.

## Documentation

- `ARCHITECTURE.md` — system architecture: numbered end-to-end flow, component
  legend, HITL state diagram, design decisions, deployment.
- [`docs/ARCHITECTURE_DIAGRAMS.md`](docs/ARCHITECTURE_DIAGRAMS.md) — the same
  system as eleven diagrams (context, layers, request lifecycle, agent
  handoffs, review state machine, guardrails, persistence), each with a short
  "what to notice".
- `docs/engineering/` — product and engineering docs:
  - `product-overview.md` — scope, users, goals
  - `agents-and-workflows.md` — agent roster, responsibilities, workflow
  - `functional-nonfunctional-requirements.md` — requirements with
    implementation evidence
  - `setup.md` — install, configuration, run instructions
  - `testing-and-release.md` — test plan, last results, release gates
  - `use-cases-and-user-stories.md` — use cases and acceptance criteria
- **Code reference** — [`docs/code-walkthrough/INDEX.md`](docs/code-walkthrough/INDEX.md)
  (per-file guide for every module) and [`docs/CODE_TOUR.md`](docs/CODE_TOUR.md)
  (one-page map).
- **Flow narratives** — [`docs/ANALYZE_BUTTON_WALKTHROUGH.md`](docs/ANALYZE_BUTTON_WALKTHROUGH.md)
  (step-by-step Analyze trace: full code per step with file and line range, checked
  by `python tools/verify_doc_refs.py`), then
  [`REVISION_BUTTON_WALKTHROUGH`](docs/REVISION_BUTTON_WALKTHROUGH.md) (the
  "Apply updates & re-analyze" click),
  [`MOCK_INTERVIEW_WALKTHROUGH`](docs/MOCK_INTERVIEW_WALKTHROUGH.md),
  [`PREP_COACH_WALKTHROUGH`](docs/PREP_COACH_WALKTHROUGH.md), and
  [`POST_INTERVIEW_COACH_WALKTHROUGH`](docs/POST_INTERVIEW_COACH_WALKTHROUGH.md) —
  the same treatment for the other three tabs. Diagram-first companions:
  [`CODE_PATH_ANALYZE`](docs/CODE_PATH_ANALYZE.md),
  [`CODE_PATH_PREP`](docs/CODE_PATH_PREP.md),
  [`CODE_PATH_HITL`](docs/CODE_PATH_HITL.md),
  [`CODE_PATH_MOCK_INTERVIEW`](docs/CODE_PATH_MOCK_INTERVIEW.md), and
  [`CODE_PATH_COACH`](docs/CODE_PATH_COACH.md).
- [`GLOSSARY.md`](GLOSSARY.md) — terms used across the docs.

## Layout

- `careercrew/config.py` - settings loaded from the environment
- `config/agents.yaml`, `config/tasks.yaml` - agent roles and task text
- `careercrew/models.py` - Pydantic contracts (analysis, prep, interview, review)
- `careercrew/crew.py` - crew assembly: agents, MCP servers, knowledge, typed outputs
- `careercrew/document_tools.py` - shared input logic + tool guardrails
- `careercrew/mcp_client.py` - real MCP stdio client + CrewAI `MCPServerStdio`
- `careercrew/pipeline.py` - orchestrator: run crew, parse, fallback, validate
- `careercrew/prep.py` - Interview Preparation Advisor (seniority + gap driven)
- `careercrew/interview.py` - mock interviewer: questions, evaluation, scoring
- `careercrew/coach.py` - full-memory prep and post-interview coaching chats
- `careercrew/audio.py` - whisper-1 transcription and tts-1 speech (graceful)
- `careercrew/llm.py` - small OpenAI chat helper used by the interactive agents
- `careercrew/session_store.py` - SQLite store for packages, interviews, and chats
- `careercrew/review.py` - HITL state machine (approve / reject / revise)
- `careercrew/guardrails.py` - input, tool, and per-agent output checks
- `mcp_server/server.py` - FastMCP server exposing read_resume / read_job_description
- `knowledge/resume_guidelines.md`, `knowledge/interview_guidelines.md` - agent knowledge
- `app.py` - Gradio layout and wiring
- `careercrew/callbacks_analyze.py` - Analyze, Approve, Reject, Request changes
- `careercrew/callbacks_interview.py` - mock interview + both coach chats
- `careercrew/runner.py` - runs the pipeline on a worker thread, reports the stage
- `careercrew/ui_html.py` - HTML renderers; `careercrew/ui_state.py` - named UI outputs
- `careercrew/services.py` - settings, database, and review service shared by the UI
- `careercrew/ui_css.py` - Gradio CSS; `main.py` - CLI entrypoint
- `Dockerfile` - production container image
- `tests/` - pytest suite (offline; the MCP fallback needs no key)

See `ARCHITECTURE.md` for the full walkthrough.

## Deployment

```bash
docker build -t careercrew .
docker run --rm -p 7860:7860 --env-file .env careercrew
```

The MCP server runs over stdio inside the container, so no second service is
needed.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```
