# CareerCrew architecture walkthrough

## The big picture

A user provides a resume file and a job description. Four agents run in a
fixed sequence and produce a feedback package. A human approves the final
bullets before anything is final. Every claim in the output must cite a fact
from the parsed resume; the system is designed to say "do not claim" rather
than invent experience.

## Request lifecycle

1. `main.py` (or `app.py`) validates the upload (type, size), copies the
   resume into `uploads/`, and redacts PII from the JD text. These are the
   input guardrails, applied before any LLM call.
2. `CareerCrew().crew()` builds the crew from `config/agents.yaml` and
   `config/tasks.yaml`. `crew.kickoff(inputs={...})` fills the
   `{resume_path}` and `{jd_source}` placeholders in the task descriptions.
3. Task 1, Profile Extractor, calls the `read_resume` tool and returns a
   `CandidateProfile` (Pydantic). Task 2, JD Analyzer, calls
   `fetch_job_description` and returns `JobRequirements`.
4. Task 3, Gap Analyst, receives both typed outputs as context, scores
   coverage 0-100, and labels each requirement covered, reframeable, or
   out_of_scope, returning a `GapReport`.
5. Task 4, Feedback Writer, receives the gap report and drafts bullets plus
   talking points, each bullet carrying its `cited_fact`, returning a
   `FeedbackDraft`.
6. Day 3: `validate_citations` checks the draft, and the HITL screen lets the
   user approve or edit. Nothing is finalized without approval.

## The four agents

- **Profile Extractor**: the only agent allowed to read the resume. Output is
  the single source of truth downstream. Its backstory forbids inferring
  employers, titles, or dates.
- **JD Analyzer**: turns prose into structure (skills, keywords, seniority,
  nice-to-haves), quoting source text per item so gaps stay traceable.
- **Gap Analyst**: the honesty core. Coverage score plus per-requirement
  verdicts. "Reframeable" means real experience can be reframed; "out of
  scope" means do not claim it.
- **Feedback Writer**: the only agent that writes user-facing prose, and only
  from cited facts. Out-of-scope items go to `do_not_claim`, never to bullets.

## Why sequential, not hierarchical

The pipeline is linear: extract, analyze JD, compare, write. There is no
delegation decision to make, so a manager agent would add latency and cost
for no benefit. Sequential is deterministic and easy to demo.

## Tools and the MCP plan

Today the agents call CrewAI `@tool` wrappers (`careercrew/tools.py`) around
the shared logic in `document_tools.py`. The same logic is already exposed as
a FastMCP server (`mcp_server/server.py`) with `read_resume_tool` and
`fetch_job_description_tool`. Day 4 swaps the wrappers for MCP-backed tools;
the logic does not change. Tool guardrails (uploads-folder confinement,
https-only fetch, timeout, byte cap) live in `document_tools.py`, next to the
code they protect.

## Guardrails, HITL, memory, knowledge

- **Input**: `redact_pii` (email, phone) + `check_upload` (type, 5 MB limit),
  applied in `main.py`/`app.py` before kickoff.
- **Output**: `validate_citations` (stub; Day 3 implements the check: every
  bullet needs a non-empty citation to a real profile fact; fail closed).
- **Tool**: allowlist and limits inside `document_tools.py`.
- **HITL**: `app.py` has the approve/edit screen wired to a stub; Day 3
  persists the approval and re-runs the citation check on edited text.
- **Memory**: `memory=True` on the crew gives short-term memory within a
  session so later agents reuse the extracted profile. No cross-session memory
  in v1 (privacy).
- **Knowledge** (Day 3): a small base of strong bullet patterns used as style
  reference only; facts always come from the profile.

## Deployment (Week 4)

Hugging Face Spaces running `app.py` with secrets in Space settings. The
Space URL is the demo link for the October 22 presentation.

## Day 2 / 3 / 4 build plan

- Day 2 (this scaffold): agents.yaml, tasks.yaml, typed outputs, sequential
  crew, CLI + UI shell run end to end.
- Day 3: knowledge base, `validate_citations`, real HITL persistence,
  guardrail trip tests (PII input, oversized file, injection in JD).
- Day 4: connect the MCP server, verify each agent actually calls it,
  confirm the MCP purpose statement for the review.

## Reading order for learning the codebase

1. `config/agents.yaml` + `config/tasks.yaml` (what the crew is)
2. `careercrew/models.py` (the contracts between agents)
3. `careercrew/crew.py` (how YAML becomes a running crew)
4. `careercrew/document_tools.py` (tools + their guardrails)
5. `mcp_server/server.py` (the same tools over MCP)
6. `main.py`, then `app.py` (entrypoints)
