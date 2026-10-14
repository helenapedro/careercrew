# CareerCrew architecture walkthrough

## The big picture

A user provides a resume (file or pasted text) and a job description (pasted
text or an https URL), and optionally a list of employer screening questions.
Five agents run in a fixed sequence and produce a feedback package plus an
application package. A human approves the result before anything is finalized.
Every claim in the output must trace to a resume fact or a verified answer-bank
entry; the system is designed to say "do not claim" rather than invent facts.

## Request lifecycle

1. `app.py` (or `main.py`) validates the upload (type, size), copies the resume
   into `uploads/`, and redacts PII from the JD text. These are the input
   guardrails, applied before any LLM call.
2. `pipeline.run_analysis` normalizes the resume to text (PDF/DOCX/TXT read, or
   pasted text), checks that a JD URL is reachable, then builds the crew with
   `build_crew()` and calls `kickoff(inputs=...)` with `{resume_path}` /
   `{resume_text}`, `{jd_source}`, and `{screening_questions}`.
3. Task 1, Profile Extractor, calls the MCP `read_resume` tool (or uses pasted
   text) and returns a `CandidateProfile`.
4. Task 2, JD Analyzer, calls the MCP `fetch_job_description` tool and returns
   `JobRequirements`.
5. Task 3, Gap Analyst, receives both typed outputs as context, scores coverage
   0-100, and labels each requirement covered, reframeable, or out_of_scope,
   returning a `GapReport`.
6. Task 4, Feedback Writer, drafts bullets plus talking points, each bullet
   carrying its `cited_fact`, returning a `FeedbackDraft`.
7. Task 5, Application Packager, calls the MCP `query_answer_bank` tool per
   screening question and returns an `ApplicationPackage`. Unknown questions go
   to `do_not_claim`.
8. `validate_citations` and `validate_package` check the draft, and the HITL
   buttons let the user approve, edit, or reject. Nothing is finalized without
   approval.

## The five agents

- **Profile Extractor**: the only agent allowed to read the resume. Output is
  the single source of truth downstream. Its backstory forbids inferring
  employers, titles, or dates.
- **JD Analyzer**: turns prose into structure (skills, keywords, seniority,
  nice-to-haves), quoting source text per item so gaps stay traceable.
- **Gap Analyst**: the honesty core. Coverage score plus per-requirement
  verdicts. "Reframeable" means real experience can be reframed; "out of scope"
  means do not claim it.
- **Feedback Writer**: the only agent that writes user-facing prose, and only
  from cited facts. Out-of-scope items go to `do_not_claim`, never to bullets.
- **Application Packager**: answers screening questions **only** from the
  verified answer bank (MCP `query_answer_bank`). Never invents work
  authorization, notice-period, location, or salary facts.

## Why sequential, not hierarchical

The pipeline is linear: extract, analyze JD, compare, write, package. There is
no delegation decision to make, so a manager agent would add latency and cost
for no benefit. Sequential is deterministic and easy to demo.

## Input handling

Input is normalized to plain text before the crew runs, so agents never care
where it came from.

- Resume file: `.pdf` (pypdf), `.docx` (python-docx), `.txt` — read under
  uploads-folder confinement.
- Resume pasted text: normalized through `read_resume_text`.
- Job description: pasted text, or an `https://` URL fetched with a timeout,
  byte cap, and an HTML/text content-type check. Anything else raises
  `JobDescriptionError` with a user-facing message.

## Tools and MCP

`careercrew/document_tools.py` is the single source of truth. `mcp_server/server.py`
exposes it as three MCP tools; `careercrew/mcp_client.py` provides both a real
stdio `MCPToolClient` (used by tests and the deterministic fallback) and a
CrewAI `MCPServerStdio` config the agents use natively. Tool guardrails
(uploads-folder confinement, https-only fetch, timeout, byte cap) live in
`document_tools.py`, next to the code they protect.

## Guardrails, HITL, memory, knowledge

- **Input**: `validate_request` (exactly one resume source, non-empty JD, no
  injection patterns) + `redact_pii` + `check_upload` (type, 5 MB limit).
- **Output**: `validate_citations` (every bullet cites a real profile fact) and
  `validate_package` (every screening answer must be `source == "answer_bank"`).
  Fails closed.
- **Tool**: allowlist and limits inside `document_tools.py`.
- **HITL**: `careercrew/review.py` enforces
  `DRAFT -> PENDING_REVIEW -> APPROVED / REJECTED`, with a bounded `REVISE`. The
  UI wires approve / revise / reject; nothing is auto-approved.
- **Memory**: `memory=True` on the crew gives short-term memory within a session
  so later agents reuse the extracted profile.
- **Knowledge**: `knowledge/resume_guidelines.md` is loaded as agent knowledge
  (writing patterns + honesty rules); facts always come from the profile or the
  answer bank.

## Deployment

Hugging Face Spaces running `app.py` (Docker SDK), secrets in Space settings.
The MCP server runs over stdio inside the container, so no second service is
needed. The Space URL is the demo link for the final presentation.

## Reading order for learning the codebase

1. `config/agents.yaml` + `config/tasks.yaml` (what the crew is)
2. `careercrew/models.py` (the contracts between agents)
3. `careercrew/crew.py` (how YAML becomes a running crew with MCP + knowledge)
4. `careercrew/document_tools.py` (tools + their guardrails + the answer bank)
5. `careercrew/pipeline.py` (orchestration, parsing, fallback, validation)
6. `careercrew/review.py` + `careercrew/session_store.py` (HITL + tracker)
7. `mcp_server/server.py` (the same tools over MCP)
8. `app.py`, then `main.py` (entrypoints)
