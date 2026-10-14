# CareerCrew

Multi-agent resume, interview, and job-application coach built with CrewAI and
MCP (CS529 Project Work 2). Five specialized agents turn a resume and a job
description into honest, cited feedback: coverage scoring, gap analysis, tailored
bullet rewrites, interview talking points, and an assembled application package
whose screening answers come **only** from a verified answer bank. A human
approves, edits, or rejects the package before it is finalized.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # then put your OPENAI_API_KEY in .env
```

Run the crew on the samples (fictional test data):

```bash
python main.py --resume samples/sample_resume.txt --jd samples/sample_jd.txt \
  --screening "Are you authorized to work in the US?" \
  --screening "What is your notice period?"
```

Pasted resume text and a JD URL also work:

```bash
python main.py --resume-text "JANE DOE. Python, FastAPI, AWS." --jd-url https://example.com/job
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
screening-answer retrieval and says so in the UI banner. Add a key for the full
five-agent crew.

## Input rules

- **Resume** — upload a `.pdf`, `.docx`, or `.txt` file **or** paste the resume
  text. Provide exactly one.
- **Job description** — paste the text **or** give an `https://` URL. A URL that
  cannot be directly accessed (non-https, unreachable, timeout, a direct file
  link, or a blocked/login page) raises a clear error that the UI shows in its
  error box; paste the text instead.

## Layout

- `careercrew/config.py` - settings loaded from the environment
- `config/agents.yaml`, `config/tasks.yaml` - agent roles and task text
- `careercrew/models.py` - Pydantic output contracts for every task and the review/tracker
- `careercrew/crew.py` - crew assembly: agents, MCP servers, knowledge, typed outputs
- `careercrew/document_tools.py` - shared input logic + tool guardrails + answer bank
- `careercrew/mcp_client.py` - real MCP stdio client + CrewAI `MCPServerStdio`
- `careercrew/pipeline.py` - orchestrator: run crew, parse, fallback, validate
- `careercrew/session_store.py` - SQLite session tracker and review history
- `careercrew/review.py` - HITL state machine (approve / reject / revise)
- `careercrew/guardrails.py` - input, tool, and output checks
- `mcp_server/server.py` - FastMCP server exposing read_resume / fetch_job_description / query_answer_bank
- `data/answer_bank.yaml` - the verified screening facts (set `verified: true` to allow)
- `knowledge/resume_guidelines.md` - writing and honesty guidelines given to the agents
- `app.py` - Gradio UI; `main.py` - CLI entrypoint
- `tests/` - pytest suite (offline; the MCP fallback needs no key)

See `ARCHITECTURE.md` for the full walkthrough.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```
