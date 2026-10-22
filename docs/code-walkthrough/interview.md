# Walkthrough: `careercrew/interview.py`

**File purpose:** Mock interviewer **logic** (questions, evaluate, overall, turns). Gradio wiring is in `app.py`.

**Flow:** [CODE_PATH_MOCK_INTERVIEW.md](../CODE_PATH_MOCK_INTERVIEW.md)

---

## IDs / helpers

- `make_session_id()` → `int-{8 hex}`
---

## `generate_questions(profile, requirements, gaps, plan, count, llm=None)`

**What:** If `llm` → prompt + `_parse_questions`; if empty/fail → `_fallback_questions` from risks, requirements, prep themes.  
**Why:** Grounded questions even offline.  

### `_build_question_prompt` / `_parse_questions` / `_fallback_questions`

JSON schema for questions; fallback builds concrete “Tell me about X” items from highest-priority gaps first.

---

## `evaluate_answer(question, answer, context, llm=None)`

**What:** LLM critique JSON or `_fallback_evaluation` (keyword overlap / length heuristics → score + strengths/improvements).  
**Guardrails:** Callers run `validate_evaluation`.  
**Fields:** score, what_interviewer_wanted, strengths, improvements, model_answer_outline.

### Prompt / parse / fallback helpers

Same pattern as questions: try LLM, repair JSON, else deterministic.

---

## `append_turn(session, role, text, question_index, audio_ref="")`

**What:** Append `TranscriptTurn`; optionally validate via guardrails.  
**Why:** Live synchronized transcript source of truth in the session object.

---

## `overall_evaluation(session, llm=None)`

**What:** Average per-question scores; LLM or `_fallback_summary` for narrative.  
**Sets:** Used by app to mark `completed=True`.

---

## How it connects

`callbacks_interview.interview_start` / `interview_submit` + `audio` + `llm.callable_or_none()`.
