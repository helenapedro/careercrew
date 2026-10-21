# Code path: Virtual mock interviewer

Voice (or text) practice interview grounded in the Analyze result: questions,
live transcript, per-question feedback, overall score. **Practice only — nothing
is submitted.**

**Prerequisite:** Analyze must have run (`ctx_state` populated).  
**UI tab:** **Mock interview**.

---

## 1. Modules

| Module | Role |
|--------|------|
| [`careercrew/callbacks_interview.py`](../careercrew/callbacks_interview.py) `interview_start`, `interview_submit`, `_ask_question` | Gradio handlers |
| [`careercrew/interview.py`](../careercrew/interview.py) | Questions, evaluate, overall score, turns |
| [`careercrew/audio.py`](../careercrew/audio.py) | `whisper-1` STT, `tts-1` TTS |
| [`careercrew/llm.py`](../careercrew/llm.py) | Chat completions for Q/eval (optional) |
| [`careercrew/guardrails.py`](../careercrew/guardrails.py) | `validate_interview_answer`, `validate_evaluation`, `validate_transcript_turn` |
| [`careercrew/session_store.py`](../careercrew/session_store.py) | `interview_sessions`, `interview_turns` |

---

## 2. Start interview

UI: **Start interview** + slider (3–10 questions).

| # | Step | Code | I/O |
|---|------|------|-----|
| 1 | Load Analyze context | `_load_context(ctx_state)` → `_context_models` | Memory |
| 2 | Generate questions | `interview.generate_questions(profile, requirements, gaps, prep_plan, n, llm=...)` | Optional OpenAI chat |
| 3 | Create session | `MockInterviewSession(session_id=make_session_id(), questions=...)` | Memory |
| 4 | Ask Q0 | `_ask_question(session, 0)` | See below |

**Question generation:**

- With LLM: prompt from `_build_question_prompt` → parse JSON list of `{text, intent, target_competency}`  
- Without / parse fail: `_fallback_questions` from gaps, prep risk areas, requirements (still grounded)  

Each `InterviewQuestion` gets an `index`.

---

## 3. Ask one question (`_ask_question`)

| # | Step | Code | I/O |
|---|------|------|-----|
| 1 | TTS | `audio.speak(question.text)` → temp audio file or `None` | OpenAI `tts-1` if key; else text-only |
| 2 | Store audio ref | `question.audio_ref` | Path string |
| 3 | Transcript turn | `interview.append_turn(..., INTERVIEWER, text)` | In-session list |
| 4 | Persist | `_STORE.save_interview(session)` | SQLite `interview_sessions` (+ turns as implemented) |
| 5 | Render | `_question_html`, Gradio `Audio` autoplay, chatbot transcript | UI |

`audio_available()` / missing key → no crash; question shown as text.

---

## 4. Submit answer (`interview_submit`)

UI: mic recorder and/or typed text → **Submit answer**.

| # | Step | Code | I/O |
|---|------|------|-----|
| 1 | Prefer STT | `audio.transcribe(answer_audio)` | OpenAI `whisper-1` if audio path |
| 2 | Else typed text | `answer_text` | UI |
| 3 | Input guardrail | `validate_interview_answer(answer)` | Reject empty/oversized/injection |
| 4 | Evaluate | `interview.evaluate_answer(question, answer, context_bundle, llm=...)` | Optional LLM; else heuristic `_fallback_evaluation` |
| 5 | Eval guardrail | `validate_evaluation(evaluation)` | Warnings; score 0–100 |
| 6 | Append candidate turn | `append_turn(..., CANDIDATE, answer, audio_ref=...)` | Session |
| 7a | More questions? | `_ask_question(session, next_index)` + show `_evaluation_html` | TTS + DB |
| 7b | Last answer? | `overall_evaluation(session)` → `completed=True` | Optional LLM summary |

**Evaluation fields** (`AnswerEvaluation`): `score`, `what_interviewer_wanted`, `strengths`, `improvements`, `model_answer_outline`.

**Overall:** average of per-question scores + summary text.

---

## 5. Persistence schema

| Table | Purpose |
|-------|---------|
| `interview_sessions` | `session_id`, optional `package_id`, `session_json`, `overall_score`, `completed`, timestamps |
| `interview_turns` | Per turn: `session_id`, `question_index`, `role` (interviewer/candidate), `text` |

Gradio also keeps `iv_state` as `session.model_dump_json()` for the live round-trip.

---

## 6. Live transcript UI

`_turns_to_messages(session)` maps turns → Gradio Chatbot messages:

- Interviewer → `role: assistant`  
- Candidate → `role: user`  

Updated after every ask/submit so the transcript stays synchronized with voice.

---

## 7. Graceful degradation

| Condition | Behavior |
|-----------|----------|
| No `OPENAI_API_KEY` | Fallback questions + heuristic eval; no TTS/STT |
| TTS fails | Question text only; interview continues |
| STT fails / empty | Use typed answer if present |
| No Analyze context | Start button shows alert: analyze first |

---

## 8. Talking points

- Interviewer is **agentic practice**, not an authenticated human interviewer  
- Questions are grounded in JD / resume / gaps / **prep plan**  
- Scoring is advisory  
- Post-interview coach consumes this session next ([CODE_PATH_COACH.md](CODE_PATH_COACH.md))  
