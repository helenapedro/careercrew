"""One-shot generator for presentation notebooks. Run: python _build_notebooks.py"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def nb(cells: list[tuple[str, str]]) -> dict:
    out = []
    for kind, source in cells:
        lines = source.splitlines(keepends=True)
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        entry: dict = {"cell_type": kind, "metadata": {}, "source": lines}
        if kind == "code":
            entry["outputs"] = []
            entry["execution_count"] = None
        out.append(entry)
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "cells": out,
    }


def write(name: str, cells: list[tuple[str, str]]) -> None:
    path = ROOT / name
    path.write_text(json.dumps(nb(cells), indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", path.name)


write(
    "00_overview.ipynb",
    [
        (
            "markdown",
            """# CareerCrew — system overview

CareerCrew is a multi-agent preparation system built with CrewAI and MCP.
Five specialized agents analyze a resume against a job description and produce
an honest interview prep plan. The product also includes a **voice mock
interviewer** and two coaching chats.

**Nothing is submitted to a job board.** CareerCrew prepares and practices;
the candidate applies themselves.

Related docs: `ARCHITECTURE.md`, `README.md`
""",
        ),
        (
            "markdown",
            """## End-to-end flow

```
Resume + JD  →  ANALYZE (5 agents + MCP tools)
                    ↓
              Prep plan + gaps + resume feedback
                    ↓
         HITL: approve / revise / reject  (SQLite history)
                    ↓
         MOCK INTERVIEW (TTS questions ↔ STT/text answers)
                    ↓
         Coaches (prep chat + post-interview chat)
```
""",
        ),
        (
            "markdown",
            """## Five agents (Analyze)

| # | Role | Output |
|---|------|--------|
| 1 | Resume reader | Structured profile |
| 2 | JD reader | Requirements |
| 3 | Gap analyst | Coverage + gaps |
| 4 | Rewrite coach | Cited bullet rewrites |
| 5 | Prep advisor | Interview prep plan |

Tools talk to an **MCP server** exposing `read_resume_tool` and
`read_job_description_tool`.
""",
        ),
        (
            "markdown",
            """## Where voice fits

Voice is used **only** in the Mock interview tab:

| Direction | Mechanism | Module |
|-----------|-----------|--------|
| Agent → candidate | TTS (`tts-1`) + Chatbot transcript | `audio.speak` + `append_turn` |
| Candidate → agent | Mic filepath → Whisper STT (or typed text) | `audio.transcribe` |
| Evaluation | **Text only** to the chat LLM | `interview.evaluate_answer` |

The chat LLM never receives the audio file — only the transcript string.
""",
        ),
        (
            "markdown",
            """## Notebooks in this folder

| Notebook | Topic |
|----------|--------|
| `01_voice_and_transcript.ipynb` | How voice and the live transcript stay in sync |
| `02_mock_interview_flow.ipynb` | Start → ask → submit → score |
| `03_analyze_pipeline.ipynb` | Analyze button → crew → fallback |
| `04_hitl_and_coaches.ipynb` | Review states + coaching memory |
""",
        ),
    ],
)

write(
    "01_voice_and_transcript.ipynb",
    [
        (
            "markdown",
            """# Voice and live transcript

This notebook explains how the mock interviewer **speaks**, how the candidate
**answers by voice or text**, and how the **live transcript** stays synchronized.

**Source files**
- `app.py` — widget layout and event wiring (`iv_audio`, `iv_answer_audio`, `iv_chatbot`)
- `careercrew/callbacks_interview.py` — `interview_start`, `_ask_question`, `interview_submit`, `_turns_to_messages`
- `careercrew/audio.py` — `speak`, `transcribe`
""",
        ),
        (
            "markdown",
            """## How it works

When the interviewer asks a question, CareerCrew uses the **same text string**
twice: TTS synthesizes speech for listening, and `append_turn` adds that text
to the transcript for reading.

When the candidate answers, Gradio saves the microphone recording to a temporary
filepath. Whisper converts it to text (or the candidate can type). **Only that
text** is sent to the evaluation LLM. The answer is appended to the transcript,
then the next question is spoken and displayed the same way.

Voice and transcript are always the same underlying text — audio is I/O around it.
""",
        ),
        (
            "markdown",
            """## Architecture diagram

```
AGENT SPEAKS                          CANDIDATE ANSWERS
───────────                           ─────────────────
question.text                         mic → Gradio temp filepath
     │                                      │
     ├─► audio.speak() → .mp3               ├─► audio.transcribe() → TEXT
     │   → gr.Audio(autoplay)               │         OR typed Textbox
     │                                      │
     └─► append_turn(INTERVIEWER)           └─► append_turn(CANDIDATE)
              │                                      │
              └────────── Chatbot ←──────────────────┘
                   (_turns_to_messages)

Chat LLM / evaluate_answer sees TEXT ONLY — never the audio bytes.
```
""",
        ),
        (
            "markdown",
            """## 1. Gradio UI widgets

Defined in `app.py` (Mock interview tab widgets, wired to `callbacks_interview`):

| Widget | Role |
|--------|------|
| `iv_audio` | Interviewer player (`autoplay=True`, not interactive) |
| `iv_answer_audio` | Candidate mic (`sources=["microphone"]`, `type="filepath"`) |
| `iv_answer_text` | Optional typed fallback |
| `iv_chatbot` | Live transcript |
""",
        ),
        (
            "code",
            """# Widget configuration used in app.py (illustrative)

ui = {
    "iv_audio": {
        "label": "Interviewer (listen)",
        "autoplay": True,
        "interactive": False,  # plays TTS mp3 from _ask_question
    },
    "iv_answer_audio": {
        "sources": ["microphone"],
        "type": "filepath",  # Gradio passes a temp path into interview_submit
        "label": "Record your answer",
    },
    "iv_answer_text": {
        "label": "Or type your answer",
        "optional": True,
    },
    "iv_chatbot": {
        "label": "Interview transcript",
        "fed_by": "_turns_to_messages(session)",
    },
}

for name, cfg in ui.items():
    print(f"{name:16} -> {cfg}")
""",
        ),
        (
            "markdown",
            """## 2. Agent speaks = TTS + transcript turn

`_ask_question` in `careercrew/callbacks_interview.py`:

1. `audio.speak(question.text)` → temporary `.mp3` (or `None` if no API key)
2. `interview.append_turn(..., INTERVIEWER, question.text)`
3. Return the audio path to `iv_audio` and `_turns_to_messages(session)` to `iv_chatbot`

`audio.speak` (`careercrew/audio.py`) calls OpenAI **`tts-1`**, writes a temp mp3,
and returns the path. On failure it returns `None` and the UI stays text-only.
""",
        ),
        (
            "code",
            """# Simulate _ask_question transcript behavior (no API calls)

def speak_stub(text: str):
    \"\"\"Stand-in for audio.speak — real code writes a temp .mp3.\"\"\"
    print(f"[TTS] would synthesize: {text!r}")
    return "/tmp/careercrew_q_demo.mp3"

turns = []

def append_turn(role: str, text: str):
    turns.append({"role": role, "text": text})

question_text = "Tell me about a time you owned an API end-to-end."
audio_path = speak_stub(question_text)
append_turn("interviewer", question_text)

print("audio_path ->", audio_path)
print("turns      ->", turns)
""",
        ),
        (
            "markdown",
            """## 3. Candidate answers = mic filepath → Whisper → text

`interview_submit` in `careercrew/callbacks_interview.py`:

```python
transcript = audio.transcribe(answer_audio) if answer_audio else ""
answer = transcript.strip() or (answer_text or "").strip()
```

- Gradio recorded the mic and passed **`answer_audio`** as a filepath.
- `audio.transcribe` opens the file and calls OpenAI **`whisper-1`**.
- Voice transcript is preferred; if empty, typed text is used.
- Then `validate_interview_answer` and `evaluate_answer` run on **text only**.
""",
        ),
        (
            "code",
            """# Voice transcript preferred over typed text when both exist

def transcribe_stub(path):
    \"\"\"Stand-in for audio.transcribe — real code calls whisper-1.\"\"\"
    if not path:
        return ""
    return "I built a FastAPI service, owned deploy, and cut latency 40%."

answer_audio = "/tmp/gradio_mic_xyz.wav"   # Gradio temp filepath
answer_text = "short typed draft"         # optional

transcript = transcribe_stub(answer_audio) if answer_audio else ""
answer = transcript.strip() or (answer_text or "").strip()

print("final answer to LLM ->", answer)
print("note: chat model never sees", answer_audio)
""",
        ),
        (
            "markdown",
            """## 4. Live transcript sync

`_turns_to_messages` (`careercrew/callbacks_interview.py`) maps session turns to Gradio Chatbot messages:

| Session role | Chatbot role |
|--------------|--------------|
| `INTERVIEWER` | `"assistant"` |
| `CANDIDATE` | `"user"` |

The Chatbot is refreshed after every ask and every submit so it stays
synchronized with the spoken dialogue.
""",
        ),
        (
            "code",
            """# Same mapping as callbacks_interview._turns_to_messages

def turns_to_messages(turns):
    messages = []
    for turn in turns:
        role = "assistant" if turn["role"] == "interviewer" else "user"
        messages.append({"role": role, "content": turn["text"]})
    return messages

append_turn("candidate", answer)
append_turn("interviewer", "How did you measure that latency improvement?")

chatbot_messages = turns_to_messages(turns)
print("What the Gradio Chatbot receives:")
print()
for m in chatbot_messages:
    who = "Interviewer" if m["role"] == "assistant" else "You"
    print(f"  {who}: {m['content']}")
""",
        ),
        (
            "markdown",
            """## 5. Failure-tolerant design

| Failure | Behavior |
|---------|----------|
| No OpenAI key | `audio_available()` is false → text-only interview |
| TTS fails | Question still shown as HTML text |
| STT fails / no mic | Typed `iv_answer_text` still works |
| Empty answer | Guardrail rejects; candidate is asked again |

`audio.py` catches exceptions and returns `""` / `None` so audio problems
never crash the UI.
""",
        ),
        (
            "markdown",
            """## Code reference

| Step | File | Symbol |
|------|------|--------|
| Mic + speaker UI | `app.py` | `iv_answer_audio`, `iv_audio`, `iv_chatbot` |
| Ask (TTS + turn) | `callbacks_interview.py` | `_ask_question` |
| Submit (STT + eval) | `callbacks_interview.py` | `interview_submit` |
| Transcript map | `callbacks_interview.py` | `_turns_to_messages` |
| Whisper / TTS | `careercrew/audio.py` | `transcribe`, `speak` |
| Persist text | `session_store.py` | `save_interview` |

Continue with `02_mock_interview_flow.ipynb` for the full interview loop.
""",
        ),
    ],
)

write(
    "02_mock_interview_flow.ipynb",
    [
        (
            "markdown",
            """# Mock interview — full round-trip

This notebook covers the complete mock-interview lifecycle: start, generate
questions, ask, evaluate each answer, then move to the next question or compute
an overall score.

**Source files**
- `careercrew/callbacks_interview.py` — `interview_start`, `_ask_question`, `interview_submit`
- `careercrew/interview.py` — `generate_questions`, `evaluate_answer`, `append_turn`, `overall_evaluation`
- Detail doc: `docs/CODE_PATH_MOCK_INTERVIEW.md`
""",
        ),
        (
            "markdown",
            """## Overview

The mock interview requires Analyze context first (`ctx_state`).

On **Start**, CareerCrew generates grounded questions from the resume, JD, gaps,
and prep plan, then asks question zero with TTS and a transcript line.

On each **Submit**: STT or typed text → guardrail → evaluate → append the
candidate turn → either ask the next question the same way, or compute an
overall score when finished.

This is practice only — nothing is submitted to an employer.
""",
        ),
        (
            "markdown",
            """## Flowchart

```
[Analyze done] ctx_state
        │
        ▼
 interview_start
   generate_questions(profile, requirements, gaps, prep_plan, n, llm)
   MockInterviewSession(...)
        │
        ▼
 _ask_question(0)  ──► TTS + INTERVIEWER turn + Chatbot
        │
        ▼
 interview_submit  ◄── mic filepath and/or typed text
   transcribe → answer text
   validate_interview_answer
   evaluate_answer → AnswerEvaluation
   append_turn(CANDIDATE)
        │
        ├── more questions? → _ask_question(next)
        └── last? → overall_evaluation → completed=True
```
""",
        ),
        (
            "markdown",
            """## Step A — `interview_start`

1. `_load_context(ctx_state)` — must exist, or show “Analyze first”.
2. `interview.generate_questions(...)` — LLM JSON list, or `_fallback_questions` from gaps/prep.
3. Build `MockInterviewSession` with a new `session_id`.
4. Return `_ask_question(session, 0)`.
""",
        ),
        (
            "code",
            """# Offline model of question generation + session start

from dataclasses import dataclass, field

@dataclass
class Question:
    index: int
    text: str
    intent: str = ""

@dataclass
class Session:
    session_id: str
    questions: list
    turns: list = field(default_factory=list)
    evaluations: list = field(default_factory=list)
    completed: bool = False
    overall_score: int = 0

def fallback_questions(gaps, n=3):
    \"\"\"Mirrors interview._fallback_questions: questions grounded in gaps.\"\"\"
    base = [f"How would you approach: {g}?" for g in gaps] or [
        "Walk me through a recent project you owned."
    ]
    while len(base) < n:
        base.append(f"Follow-up competency question #{len(base)+1}")
    return [Question(i, t, intent="grounded practice") for i, t in enumerate(base[:n])]

gaps = ["system design for APIs", "ownership of production incidents", "Python typing"]
session = Session("iv-demo-001", fallback_questions(gaps, n=3))
print("session", session.session_id)
for q in session.questions:
    print(f"  Q{q.index}: {q.text}")
""",
        ),
        (
            "markdown",
            """## Step B — `_ask_question`

| Action | Code |
|--------|------|
| TTS | `audio.speak(question.text)` |
| Transcript | `append_turn(INTERVIEWER, question.text)` |
| Persist | `_STORE.save_interview(session)` |
| UI output | question HTML, audio path, chatbot messages, `iv_state` JSON |
""",
        ),
        (
            "code",
            """def ask_question(session: Session, index: int):
    q = session.questions[index]
    print(f"[TTS] {q.text}")
    session.turns.append({"role": "interviewer", "q": index, "text": q.text})
    return q

ask_question(session, 0)
print("turns so far:", session.turns)
""",
        ),
        (
            "markdown",
            """## Step C — `interview_submit`

Prefer STT over typed text → validate → `evaluate_answer` → append candidate turn.

**Evaluation fields:** `score`, `what_interviewer_wanted`, `strengths`,
`improvements`, `model_answer_outline`.

Then:
- if more questions remain → `_ask_question(next)` and show feedback HTML
- if this was the last answer → `overall_evaluation` (average scores + summary)
""",
        ),
        (
            "code",
            """def evaluate_stub(question: Question, answer: str) -> dict:
    \"\"\"Stand-in for interview.evaluate_answer (LLM or heuristic fallback).\"\"\"
    score = 70 if len(answer) > 40 else 45
    return {
        "score": score,
        "what_interviewer_wanted": question.intent or "a specific, owned example",
        "strengths": ["Clear ownership language"] if score >= 60 else [],
        "improvements": ["Add metrics"] if score < 80 else [],
    }

def submit(session: Session, answer: str):
    index = len(session.evaluations)
    q = session.questions[index]
    evaluation = evaluate_stub(q, answer)
    session.evaluations.append(evaluation)
    session.turns.append({"role": "candidate", "q": index, "text": answer})
    print(f"Q{index} score={evaluation['score']}")
    next_i = index + 1
    if next_i < len(session.questions):
        ask_question(session, next_i)
    else:
        session.overall_score = round(
            sum(e["score"] for e in session.evaluations) / len(session.evaluations)
        )
        session.completed = True
        print(f"DONE overall={session.overall_score}")

submit(session, "I designed the checkout API, owned deploys, and reduced p95 latency 40%.")
submit(session, "I ran the incident bridge, wrote the RCA, and added a runbook.")
submit(session, "I introduced mypy gradually and gated CI on typed modules.")
print("completed:", session.completed, "score:", session.overall_score)
print("transcript lines:", len(session.turns))
""",
        ),
        (
            "markdown",
            """## Persistence

| Store | What |
|-------|------|
| Gradio `iv_state` | `session.model_dump_json()` for the live round-trip |
| SQLite `interview_sessions` | session blob, overall score, completed |
| SQLite `interview_turns` | role + text per turn |

Audio paths may be referenced temporarily; **durable content is text**.
""",
        ),
        (
            "markdown",
            """## Code reference

| Concern | File | Symbol |
|---------|------|--------|
| Start | `callbacks_interview.py` | `interview_start` |
| Ask | `callbacks_interview.py` | `_ask_question` |
| Submit | `callbacks_interview.py` | `interview_submit` |
| Questions / eval | `interview.py` | `generate_questions`, `evaluate_answer`, `overall_evaluation` |
| Turns | `interview.py` | `append_turn` |
| Guardrails | `guardrails.py` | `validate_interview_answer`, `validate_evaluation` |

See `01_voice_and_transcript.ipynb` for STT/TTS detail.
""",
        ),
    ],
)

write(
    "03_analyze_pipeline.ipynb",
    [
        (
            "markdown",
            """# Analyze button — crew pipeline

This notebook explains what happens when the user clicks **Analyze**: Gradio
collects inputs, the pipeline builds a five-agent CrewAI crew with MCP tools,
and a typed analysis package is produced (or a deterministic fallback).

**Source files**
- `app.py` — button wiring to the analyze callback
- `careercrew/callbacks_analyze.py` — `analyze`, `approve`, `reject`, `request_revision`
- `careercrew/pipeline.py` — `run_analysis`
- `careercrew/crew.py` — `build_crew`
- `config/agents.yaml`, `config/tasks.yaml`
- Detail doc: `docs/CODE_PATH_ANALYZE.md`
""",
        ),
        (
            "markdown",
            """## Overview

Analyze is the core of CareerCrew. Gradio gathers the resume and JD (upload or
paste), runs input guardrails, then `pipeline.run_analysis` builds a CrewAI crew
of five agents with MCP tools.

The crew produces a typed package: profile, requirements, gaps, rewrites, and a
prep plan. If the LLM crew fails, CareerCrew still returns a
**gap-based fallback** so the demo keeps working. The result is
submitted into HITL review and rendered across the UI tabs.
""",
        ),
        (
            "markdown",
            """## Call chain

```
Gradio Analyze
   callbacks_analyze.analyze
      resolve uploads / paste
      guardrails.validate_request
      pipeline.run_analysis
         build_crew (agents.yaml + tasks.yaml + MCP)
         crew.kickoff
         parse → Pydantic models
         OR gap-based fallback (prep.build_fallback_plan)
      review.submit_for_review
      session_store persist
   render Match / Prep tabs
```
""",
        ),
        (
            "markdown",
            """## Agents and tools

| Piece | Location |
|-------|----------|
| Agent roles | `config/agents.yaml` |
| Task prompts | `config/tasks.yaml` |
| Crew wiring | `careercrew/crew.py` → `build_crew` |
| Shared tool logic | `careercrew/document_tools.py` |
| MCP server | `mcp_server/server.py` — `read_resume_tool`, `read_job_description_tool` |
| Contracts | `careercrew/models.py` |
| Honesty | cited resume facts only; unsupported items go to `do_not_claim` |
""",
        ),
        (
            "code",
            """# Five-step Analyze crew sequence

STEPS = [
    ("1 Resume reader", "Structured CandidateProfile"),
    ("2 JD reader", "JobRequirements"),
    ("3 Gap analyst", "Coverage score + GapReport"),
    ("4 Rewrite coach", "Cited resume rewrites"),
    ("5 Prep advisor", "InterviewPrepPlan (seniority-aware)"),
]

print("Analyze crew sequence")
for name, out in STEPS:
    print(f"  {name:20} -> {out}")

print()
print("Fallback:")
print("  crew fails / no key -> gap-based prep plan")
print("  still grounded in the resume and the job description")
""",
        ),
        (
            "markdown",
            """## Guardrails

- **Input:** file type/size, one resume source, one JD source, no raw job-board scrape.
- **Tools:** upload confinement.
- **Output:** Pydantic validation; prep advice stays grounded in real gaps.

Implementation: `careercrew/guardrails.py`.
""",
        ),
        (
            "markdown",
            """## Code reference

| Step | File | Symbol |
|------|------|--------|
| UI | `callbacks_analyze.py` | `analyze` |
| Orchestrator | `pipeline.py` | `run_analysis`, `build_fallback_plan` |
| Crew | `crew.py` | `build_crew` |
| MCP | `mcp_server/server.py` | two tools |
| HITL handoff | `review.py` | `submit_for_review` |

Continue with `04_hitl_and_coaches.ipynb`.
""",
        ),
    ],
)

write(
    "04_hitl_and_coaches.ipynb",
    [
        (
            "markdown",
            """# HITL review and coaching chats

This notebook covers human-in-the-loop review (approve / revise / reject),
package history (`pkg-…`), and the two coaching chats.

**Source files**
- `careercrew/review.py`
- `careercrew/session_store.py`
- `careercrew/coach.py`
- `careercrew/callbacks_analyze.py` — approve / reject / revise handlers
- `careercrew/callbacks_interview.py` — prep and post-interview coach handlers
- Detail docs: `docs/CODE_PATH_HITL.md`, `docs/CODE_PATH_COACH.md`
""",
        ),
        (
            "markdown",
            """## HITL overview

After Analyze, the package enters a human-in-the-loop state machine. The user
can **approve**, **request revision**, or **reject**. Every package gets an id
like `pkg-…`, stored in SQLite and listed under History.

CareerCrew still never auto-submits applications.
""",
        ),
        (
            "markdown",
            """## Review state machine

```
          submit_for_review
                 │
                 ▼
            PENDING
           /   |   \\
     approve revise reject
         │     │     │
         ▼     ▼     ▼
     APPROVED REVISION REJECTED
                 │
                 └──► user re-analyzes → new package
```

Allowed transitions are defined in `review.py` (`_ALLOWED`).
""",
        ),
        (
            "code",
            """# Illustrative state machine (see review.py for the real _ALLOWED map)

ALLOWED = {
    "PENDING": {"APPROVED", "REVISION_REQUESTED", "REJECTED"},
    "REVISION_REQUESTED": {"PENDING"},
    "APPROVED": set(),
    "REJECTED": set(),
}

def transition(state: str, action: str) -> str:
    mapping = {
        "approve": "APPROVED",
        "revise": "REVISION_REQUESTED",
        "reject": "REJECTED",
        "resubmit": "PENDING",
    }
    nxt = mapping[action]
    print(f"{state} --{action}--> {nxt}")
    return nxt

state = "PENDING"
state = transition(state, "revise")
state = transition(state, "resubmit")
state = transition(state, "approve")
""",
        ),
        (
            "markdown",
            """## Coaching chats

CareerCrew provides two Gradio chat tabs:

- **Prep coach** — helps improve the resume and preparation using Analyze memory.
- **Post-interview coach** — uses the full mock transcript, per-question
  evaluations, and overall score.

Both use the chat LLM with guardrailed replies. They are advisory only;
they do not auto-apply.
""",
        ),
        (
            "markdown",
            """## Coach memory bundles

| Coach | Typical context |
|-------|-----------------|
| Prep coach | Profile, gaps, rewrites, prep plan |
| Post-interview coach | Same + interview turns + evaluations + overall score |

Implementation: `careercrew/coach.py` + Gradio handlers in `callbacks_interview.py`.
Chats persist via `session_store.py`.
""",
        ),
        (
            "code",
            """# Context available to the post-interview coach

post_interview_context = {
    "role_title": "Backend Engineer",
    "gaps": ["system design", "incident ownership"],
    "prep_plan_highlights": ["drill STAR stories for ownership"],
    "transcript": [
        {"role": "interviewer", "text": "Tell me about an API you owned."},
        {"role": "candidate", "text": "I owned checkout API and cut p95 40%."},
    ],
    "evaluations": [{"score": 78, "improvements": ["Add tradeoffs"]}],
    "overall_score": 78,
}

print("Post-interview coach can see:")
for k, v in post_interview_context.items():
    kind = type(v).__name__
    shown = v if not isinstance(v, list) else f"{len(v)} items"
    print(f"  • {k}: {kind} = {shown}")
""",
        ),
        (
            "markdown",
            """## Code reference

| Concern | File | Symbol |
|---------|------|--------|
| State machine | `review.py` | approve / revise / reject helpers |
| History data | `session_store.py` | `list_packages`; rows built in `ui_state.py` |
| SQLite | `session_store.py` | packages, chats, interviews |
| Coaches | `coach.py` | prep + post-interview reply builders |

Voice / transcript detail: `01_voice_and_transcript.ipynb`
""",
        ),
    ],
)

print("done")
