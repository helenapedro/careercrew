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
            """# CareerCrew — presentation overview

**Goal of this notebook:** one-slide mental model before diving into code.

**Open beside this:** `ARCHITECTURE.md`, `README.md`
""",
        ),
        (
            "markdown",
            """## Say this (30 seconds)

> CareerCrew is a **multi-agent prep system**. Six CrewAI agents analyze a resume against a job description, build an honest prep plan, and draft screening answers **only** from a verified answer bank. On top of that we add a **voice mock interviewer** and coaching chats. **Nothing is submitted** to a job board — we prepare and practice only.
""",
        ),
        (
            "markdown",
            """## End-to-end picture

```
Resume + JD  →  ANALYZE (6 agents + MCP tools)
                    ↓
              Prep plan + gaps + screening answers
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
            """## Six agents (Analyze)

| # | Role | Output |
|---|------|--------|
| 1 | Resume reader | Structured profile |
| 2 | JD reader | Requirements |
| 3 | Gap analyst | Coverage + gaps |
| 4 | Rewrite coach | Cited bullet rewrites |
| 5 | Prep advisor | Interview prep plan |
| 6 | Screening drafter | Answers from answer bank only |

Tools talk to an **MCP server** (`read_resume`, `read_job_description`, `query_answer_bank`).
""",
        ),
        (
            "markdown",
            """## Where voice fits

Voice is **only** in the Mock interview tab:

| Direction | Mechanism | Module |
|-----------|-----------|--------|
| Agent → you | TTS (`tts-1`) + Chatbot transcript | `audio.speak` + `append_turn` |
| You → agent | Mic filepath → Whisper STT (or typed text) | `audio.transcribe` |
| Eval | **Text only** to chat LLM | `interview.evaluate_answer` |

> **Key honesty line:** the chat LLM never receives the audio file — only the transcript string.
""",
        ),
        (
            "markdown",
            """## Presentation map

| Notebook | Topic |
|----------|--------|
| `01_voice_and_transcript.ipynb` | How voice + live transcript stay in sync |
| `02_mock_interview_flow.ipynb` | Start → ask → submit → score |
| `03_analyze_pipeline.ipynb` | Analyze button → crew → fallback |
| `04_hitl_and_coaches.ipynb` | Review states + coaching memory |

Speaker minute order: `docs/SPEAKER_CHEATSHEET.md`
""",
        ),
    ],
)

write(
    "01_voice_and_transcript.ipynb",
    [
        (
            "markdown",
            """# How the agent talks to us — and how we talk back

**Focus:** voice in, voice out, and the **live transcript** Chatbot.

**Open beside this:**
- `app.py` → `iv_audio`, `iv_answer_audio`, `_ask_question`, `interview_submit`, `_turns_to_messages`
- `careercrew/audio.py` → `speak`, `transcribe`
""",
        ),
        (
            "markdown",
            """## Say this (20 seconds)

> When the interviewer asks a question, we take the **same text string**, synthesize speech with TTS for the ear, and append that string as an interviewer turn for the eye. When I answer, Gradio saves my mic to a temp file; Whisper turns it into text (or I type). Only that text goes to the evaluator. Then we append my answer to the transcript and speak the next question the same way. **Voice and transcript are always the same underlying text — audio is just I/O around it.**
""",
        ),
        (
            "markdown",
            """## Board diagram

```
AGENT SPEAKS                          YOU ANSWER
───────────                           ──────────
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
            """## 1. UI widgets (Gradio) — where the mic and speaker live

File: `app.py` (Mock interview tab, ~1363–1378)

| Widget | Role |
|--------|------|
| `iv_audio` | Interviewer player (`autoplay=True`, not interactive) |
| `iv_answer_audio` | Your mic (`sources=["microphone"]`, `type="filepath"`) |
| `iv_answer_text` | Optional typed fallback |
| `iv_chatbot` | Live transcript |
""",
        ),
        (
            "code",
            """# Exact shapes from app.py (illustrative — not importing Gradio here)

ui = {
    "iv_audio": {
        "label": "Interviewer (listen)",
        "autoplay": True,
        "interactive": False,  # plays TTS mp3 from _ask_question
    },
    "iv_answer_audio": {
        "sources": ["microphone"],
        "type": "filepath",  # Gradio passes a temp path string into interview_submit
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
    print(f"{name:16} → {cfg}")
""",
        ),
        (
            "markdown",
            """## 2. Agent talks = TTS + transcript turn

`_ask_question` in `app.py` (~1043–1060):

1. `audio.speak(question.text)` → temp `.mp3` (or `None` if no key)
2. `interview.append_turn(..., INTERVIEWER, question.text)`
3. Return path to `iv_audio` **and** `_turns_to_messages(session)` to `iv_chatbot`

`audio.speak` (`careercrew/audio.py`): OpenAI **`tts-1`** → write temp mp3 → return path. On failure → `None` (text-only mode).
""",
        ),
        (
            "code",
            """# Simulate what _ask_question does with the transcript (no API calls)

def speak_stub(text: str):
    \"\"\"Stand-in for audio.speak — real code writes a temp .mp3.\"\"\"
    print(f"[TTS] would synthesize: {text!r}")
    return "/tmp/careercrew_q_demo.mp3"  # fake path for the demo

turns = []  # like session.turns

def append_turn(role: str, text: str):
    turns.append({"role": role, "text": text})

question_text = "Tell me about a time you owned an API end-to-end."
audio_path = speak_stub(question_text)
append_turn("interviewer", question_text)

print("audio_path →", audio_path)
print("turns      →", turns)
""",
        ),
        (
            "markdown",
            """## 3. You talk = mic filepath → Whisper → text

`interview_submit` in `app.py` (~1092–1094):

```python
transcript = audio.transcribe(answer_audio) if answer_audio else ""
answer = transcript.strip() or (answer_text or "").strip()
```

- Gradio recorded the mic and passed **`answer_audio`** as a filepath.
- `audio.transcribe` opens the file → OpenAI **`whisper-1`** → string.
- Prefer voice transcript; if empty, use typed text.
- Then `validate_interview_answer` + `evaluate_answer` (chat LLM, **text only**).
""",
        ),
        (
            "code",
            """# Simulate STT preference: voice wins over typed text when both exist

def transcribe_stub(path):
    \"\"\"Stand-in for audio.transcribe — real code calls whisper-1.\"\"\"
    if not path:
        return ""
    return "I built a FastAPI service, owned deploy, and cut latency 40%."

answer_audio = "/tmp/gradio_mic_xyz.wav"   # Gradio temp filepath
answer_text = "short typed draft"         # optional

transcript = transcribe_stub(answer_audio) if answer_audio else ""
answer = transcript.strip() or (answer_text or "").strip()

print("final answer to LLM →", answer)
print("note: chat model never sees", answer_audio)
""",
        ),
        (
            "markdown",
            """## 4. Live transcript sync

`_turns_to_messages` (`app.py` ~926–932):

| Session role | Chatbot role |
|--------------|--------------|
| `INTERVIEWER` | `"assistant"` |
| `CANDIDATE` | `"user"` |

Updated after every ask and every submit so the Chatbot stays synchronized with voice.
""",
        ),
        (
            "code",
            """# Same mapping as app._turns_to_messages

def turns_to_messages(turns):
    messages = []
    for turn in turns:
        role = "assistant" if turn["role"] == "interviewer" else "user"
        messages.append({"role": role, "content": turn["text"]})
    return messages

# Continue the mock session from earlier cells
append_turn("candidate", answer)
append_turn("interviewer", "How did you measure that latency improvement?")

chatbot_messages = turns_to_messages(turns)
print("What the Gradio Chatbot receives:\\n")
for m in chatbot_messages:
    who = "Interviewer" if m["role"] == "assistant" else "You"
    print(f"  {who}: {m['content']}")
""",
        ),
        (
            "markdown",
            """## 5. Failure-tolerant design (say this if asked)

| Failure | Behavior |
|---------|----------|
| No OpenAI key | `audio_available()` false → text-only interview |
| TTS fails | Question still shown as HTML text |
| STT fails / no mic | Typed `iv_answer_text` still works |
| Empty answer | Guardrail rejects; ask again |

Never crash the UI for audio problems (`audio.py` catches exceptions → `""` / `None`).
""",
        ),
        (
            "markdown",
            """## Code checklist for the professor

| Step | File | Symbol |
|------|------|--------|
| Mic + speaker UI | `app.py` | `iv_answer_audio`, `iv_audio`, `iv_chatbot` |
| Ask (TTS + turn) | `app.py` | `_ask_question` |
| Submit (STT + eval) | `app.py` | `interview_submit` |
| Transcript map | `app.py` | `_turns_to_messages` |
| Whisper / TTS | `careercrew/audio.py` | `transcribe`, `speak` |
| Persist text | `session_store.py` | `save_interview` |

**Next notebook:** `02_mock_interview_flow.ipynb` (full start → score loop).
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

**Focus:** Start → generate questions → ask → evaluate → next / overall score.

**Open beside this:**
- `app.py` → `interview_start`, `_ask_question`, `interview_submit`
- `careercrew/interview.py` → `generate_questions`, `evaluate_answer`, `append_turn`, `overall_evaluation`
- Detail doc: `docs/CODE_PATH_MOCK_INTERVIEW.md`
""",
        ),
        (
            "markdown",
            """## Say this (25 seconds)

> The mock interview needs Analyze context first. On Start we generate grounded questions from the resume, JD, gaps, and prep plan. We ask question zero with TTS and a transcript line. Each Submit: STT or text → guardrail → evaluate → append your turn → either ask the next question the same way, or compute an overall score when finished. Practice only — nothing is submitted.
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

1. `_load_context(ctx_state)` — must exist or show “Analyze first”.
2. `interview.generate_questions(...)` — LLM JSON list, or `_fallback_questions` from gaps/prep.
3. Build `MockInterviewSession` with a new `session_id`.
4. Return `_ask_question(session, 0)`.
""",
        ),
        (
            "code",
            """# Tiny offline model of question generation + session start

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
    \"\"\"Mirrors interview._fallback_questions idea: grounded in gaps.\"\"\"
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
| UI out | question HTML, audio path, chatbot messages, `iv_state` JSON |
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

**Evaluation fields:** `score`, `what_interviewer_wanted`, `strengths`, `improvements`, `model_answer_outline`.

Then:
- if more questions → `_ask_question(next)` + show feedback HTML
- if last → `overall_evaluation` (average scores + summary)
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

Audio paths may be referenced; **durable content is text**.
""",
        ),
        (
            "markdown",
            """## Code checklist

| Concern | File | Symbol |
|---------|------|--------|
| Start | `app.py` | `interview_start` |
| Ask | `app.py` | `_ask_question` |
| Submit | `app.py` | `interview_submit` |
| Questions / eval | `interview.py` | `generate_questions`, `evaluate_answer`, `overall_evaluation` |
| Turns | `interview.py` | `append_turn` |
| Guardrails | `guardrails.py` | `validate_interview_answer`, `validate_evaluation` |

**Related:** `01_voice_and_transcript.ipynb` for STT/TTS detail.
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

**Focus:** what happens when the user clicks **Analyze**.

**Open beside this:**
- `app.py` → `analyze`
- `careercrew/pipeline.py` → `run_analysis`
- `careercrew/crew.py` → `build_crew`
- `config/agents.yaml`, `config/tasks.yaml`
- `docs/CODE_PATH_ANALYZE.md`
""",
        ),
        (
            "markdown",
            """## Say this (30 seconds)

> Analyze is the core. Gradio gathers resume and JD (upload or paste), runs input guardrails, then `pipeline.run_analysis` builds a CrewAI crew of six agents with MCP tools. They produce a typed package: profile, requirements, gaps, rewrites, prep plan, screening answers. If the LLM crew fails, we still return a **deterministic fallback package** so the demo never dies. The result is submitted into HITL review and shown across the UI tabs.
""",
        ),
        (
            "markdown",
            """## Call chain

```
Gradio Analyze
   app.analyze
      resolve uploads / paste
      guardrails.validate_request
      pipeline.run_analysis
         build_crew (agents.yaml + tasks.yaml + MCP)
         crew.kickoff
         parse → Pydantic models
         OR deterministic_package (fallback)
      review.submit_for_review
      session_store persist
   render Match / Prep / Screening tabs
```
""",
        ),
        (
            "markdown",
            """## Agents & tools (what to point at)

| Piece | Location |
|-------|----------|
| Agent roles | `config/agents.yaml` |
| Task prompts | `config/tasks.yaml` |
| Crew wiring | `careercrew/crew.py` → `build_crew` |
| Shared tool logic | `careercrew/document_tools.py` |
| MCP server | `mcp_server/server.py` — `read_resume`, `read_job_description`, `query_answer_bank` |
| Contracts | `careercrew/models.py` |
| Honesty | `data/answer_bank.yaml` (`verified: true` only) |
""",
        ),
        (
            "code",
            """# Chalkboard: six-step pipeline as a list (no CrewAI import needed)

STEPS = [
    ("1 Resume reader", "Structured CandidateProfile"),
    ("2 JD reader", "JobRequirements"),
    ("3 Gap analyst", "Coverage score + GapReport"),
    ("4 Rewrite coach", "Cited resume rewrites"),
    ("5 Prep advisor", "InterviewPrepPlan (seniority-aware)"),
    ("6 Screening drafter", "Answers ONLY from verified answer bank"),
]

print("Analyze crew sequence")
for name, out in STEPS:
    print(f"  {name:20} -> {out}")

print()
print("Fallback story:")
print("  crew fails / no key -> pipeline.deterministic_package(...)")
print("  still grounded in gaps + answer bank retrieval")
""",
        ),
        (
            "markdown",
            """## Guardrails (say if asked)

- **Input:** file type/size, one resume source, one JD source, no raw job-board scrape.
- **Tools:** confinement for uploads; answer bank query only verified facts.
- **Output:** Pydantic validation; prep advice must stay grounded; screening never invents unverified claims.

File: `careercrew/guardrails.py`.
""",
        ),
        (
            "markdown",
            """## Code checklist

| Step | File | Symbol |
|------|------|--------|
| UI | `app.py` | `analyze` |
| Orchestrator | `pipeline.py` | `run_analysis`, `deterministic_package` |
| Crew | `crew.py` | `build_crew` |
| MCP | `mcp_server/server.py` | three tools |
| HITL handoff | `review.py` | `submit_for_review` |

**Next:** `04_hitl_and_coaches.ipynb`
""",
        ),
    ],
)

write(
    "04_hitl_and_coaches.ipynb",
    [
        (
            "markdown",
            """# HITL review + coaching chats

**Focus:** approve / revise / reject, History `pkg-…`, and the two coaches.

**Open beside this:**
- `careercrew/review.py`
- `careercrew/session_store.py`
- `careercrew/coach.py`
- `app.py` approve / reject / coach handlers
- `docs/CODE_PATH_HITL.md`, `docs/CODE_PATH_COACH.md`
""",
        ),
        (
            "markdown",
            """## Say this — HITL (20 seconds)

> After Analyze, the package enters a human-in-the-loop state machine. You can **approve**, **request revision**, or **reject**. Every package gets an id like `pkg-…` stored in SQLite and listed under History. CareerCrew still never auto-submits applications.
""",
        ),
        (
            "markdown",
            """## Review state machine (simplified)

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

Allowed transitions live in `review.py` (`_ALLOWED`).
""",
        ),
        (
            "code",
            """# Illustrative state machine (see review.py for the real _ALLOWED map)

ALLOWED = {
    "PENDING": {"APPROVED", "REVISION_REQUESTED", "REJECTED"},
    "REVISION_REQUESTED": {"PENDING"},  # after re-analyze / resubmit path
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
            """## Say this — Coaches (20 seconds)

> Two Gradio chat tabs. The **prep coach** helps improve the resume and preparation using Analyze memory. The **post-interview coach** has the full mock transcript, per-question evaluations, and overall score. Both use the chat LLM with guardrailed replies — still advisory, not auto-apply.
""",
        ),
        (
            "markdown",
            """## Coach memory bundles

| Coach | Typical context |
|-------|-----------------|
| Prep coach | Profile, gaps, rewrites, prep plan |
| Post-interview coach | Same + interview turns + evaluations + overall score |

Implementation: `careercrew/coach.py` + Gradio handlers in `app.py`.
Chats persist via `session_store.py`.
""",
        ),
        (
            "code",
            """# What "full memory" means for the post-interview coach (conceptual)

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
            """## Code checklist

| Concern | File | Symbol |
|---------|------|--------|
| State machine | `review.py` | approve / revise / reject helpers |
| History UI | `app.py` | History tab + `_tracker_rows` |
| SQLite | `session_store.py` | packages, chats, interviews |
| Coaches | `coach.py` | prep + post-interview reply builders |

**Back to voice detail:** `01_voice_and_transcript.ipynb`
""",
        ),
    ],
)

print("done")
