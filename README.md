# CareerCrew

Multi-agent resume, interview, and job-application coach built with CrewAI and
MCP (CS529 Project Work 2). Six specialized agents turn a resume and a job
description into honest, cited guidance: coverage scoring, gap analysis, tailored
bullet rewrites, a seniority-aware **interview preparation plan**, and
copy-ready screening answers that come **only** from a verified answer bank.

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
python main.py --resume samples/sample_resume.txt --jd samples/sample_jd.txt \
  --screening "Are you authorized to work in the US?" \
  --screening "What is your notice period?"
```

Pasted text and an uploaded JD file also work:

```bash
python main.py --resume-text "JANE DOE. Python, FastAPI, AWS." --jd "We need a Python engineer."
python main.py --resume samples/sample_resume.txt --jd-file samples/sample_jd.pdf
```

Run the web UI:

```bash
python app.py
```

Run the MCP server standalone (for a manual smoke test):

```bash
python -m mcp_server.server
```

The app runs without an `OPENAI_API_KEY`: it falls back to real MCP
screening-answer retrieval and a deterministic gap-based prep plan, and says so
in the UI banner. Add a key for the full crew and the voice interview.

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
- **Copy-ready screening answers** — drafted only from the verified answer bank;
  unverified questions are surfaced under "needs your input".
- **Voice mock interview** — the interviewer asks questions from the application,
  the candidate answers by voice or text, and each answer gets real-time feedback
  (what the interviewer wanted, what to improve). Speech-to-text and
  text-to-speech use the OpenAI audio API; without a key it degrades to a
  text-only interview.
- **Prep coach chat** — iterate on resume improvements and preparation.
- **Post-interview coach chat** — ask anything about performance; the coach has
  the resume, JD, gap report, prep plan, full transcript, evaluations, and score.
- **Guardrails everywhere** — input validation, PII redaction, grounded prep
  advice, bounded scoring, safe coaching replies.

## Documentation

- `ARCHITECTURE.md` — system architecture: numbered end-to-end flow, component
  legend, HITL state diagram, design decisions, deployment.
- `docs/engineering/` — product and engineering docs:
  - `product-overview.md` — scope, users, goals
  - `agents-and-workflows.md` — agent roster, responsibilities, workflow
  - `functional-nonfunctional-requirements.md` — requirements with
    implementation evidence
  - `setup.md` — install, configuration, run instructions
  - `testing-and-release.md` — test plan, last results, release gates
  - `use-cases-and-user-stories.md` — use cases and acceptance criteria
  - `careercrew-product-draft-v0.1.md` — product draft with verification notes

## Layout

- `careercrew/config.py` - settings loaded from the environment
- `config/agents.yaml`, `config/tasks.yaml` - agent roles and task text
- `careercrew/models.py` - Pydantic contracts (analysis, prep, interview, review)
- `careercrew/crew.py` - crew assembly: agents, MCP servers, knowledge, typed outputs
- `careercrew/document_tools.py` - shared input logic + tool guardrails + answer bank
- `careercrew/mcp_client.py` - real MCP stdio client + CrewAI `MCPServerStdio`
- `careercrew/pipeline.py` - orchestrator: run crew, parse, fallback, validate
- `careercrew/prep.py` - Interview Preparation Advisor (seniority + gap driven)
- `careercrew/interview.py` - mock interviewer: questions, evaluation, scoring
- `careercrew/coach.py` - full-memory prep and post-interview coaching chats
- `careercrew/audio.py` - whisper-1 transcription and tts-1 speech (graceful)
- `careercrew/llm.py` - small OpenAI chat helper used by the interactive agents
- `careercrew/session_store.py` - SQLite session tracker, interviews, and chats
- `careercrew/review.py` - HITL state machine (approve / reject / revise)
- `careercrew/guardrails.py` - input, tool, and per-agent output checks
- `mcp_server/server.py` - FastMCP server exposing read_resume / read_job_description / query_answer_bank
- `data/answer_bank.yaml` - the verified screening facts (set `verified: true` to allow)
- `knowledge/resume_guidelines.md`, `knowledge/interview_guidelines.md` - agent knowledge
- `app.py` - Gradio UI; `careercrew/ui_css.py` - Gradio CSS; `main.py` - CLI entrypoint
- `Dockerfile` - production image (also used by Hugging Face Spaces, Docker SDK)
- `tests/` - pytest suite (offline; the MCP fallback needs no key)

See `ARCHITECTURE.md` for the full walkthrough.

## Technical presentation

**Presentation notebooks (big-screen explanations + offline demos):**

- [`notebooks/README.md`](notebooks/README.md) — talk order
- `notebooks/00_overview.ipynb` → `01_voice_and_transcript.ipynb` → `02_mock_interview_flow.ipynb` → `03_analyze_pipeline.ipynb` → `04_hitl_and_coaches.ipynb`

**Professor walkthrough (open `.py` + guide side-by-side):**

- [`docs/code-walkthrough/INDEX.md`](docs/code-walkthrough/INDEX.md) — index of per-file annotated guides
- [`docs/SPEAKER_CHEATSHEET.md`](docs/SPEAKER_CHEATSHEET.md) — talk minute order

**Flow narrative (what happens after each button):**

- [`docs/CODE_PATH_ANALYZE.md`](docs/CODE_PATH_ANALYZE.md) — Analyze button end-to-end
- [`docs/CODE_PATH_PREP.md`](docs/CODE_PATH_PREP.md) — Interview Prep Advisor + fallback
- [`docs/CODE_PATH_HITL.md`](docs/CODE_PATH_HITL.md) — approve / revise / reject + History `pkg-…`
- [`docs/CODE_PATH_MOCK_INTERVIEW.md`](docs/CODE_PATH_MOCK_INTERVIEW.md) — voice/text mock interviewer
- [`docs/CODE_PATH_COACH.md`](docs/CODE_PATH_COACH.md) — Prep coach + Post-interview coach

Engineering product docs (scope, requirements, setup) live under
`docs/engineering/`.

## Deployment

```bash
docker build -t careercrew .
docker run --rm -p 7860:7860 --env-file .env careercrew
```

The same image runs on Hugging Face Spaces (Docker SDK) with secrets in the
Space settings. The MCP server runs over stdio inside the container, so no
second service is needed.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```
