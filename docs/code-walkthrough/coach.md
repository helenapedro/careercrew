# Walkthrough: `careercrew/coach.py`

**File purpose:** Full-memory coaching chats — prep (resume/prep) and post-interview (includes mock transcript). Bounded context; guardrailed replies; offline fallback.

**Flow:** [CODE_PATH_COACH.md](../CODE_PATH_COACH.md)

---

## Constants

`MAX_CONTEXT_CHARS = 12000`, `MAX_HISTORY_TURNS = 12`.

### `_guidelines()`

Read `COACHING_GUIDELINES_PATH` (interview guidelines markdown).

---

## `build_context(profile=..., requirements=..., gaps=..., prep_plan=..., interview=..., include_interview=False)`

**What:** Assemble markdown sections from model JSON; if `include_interview`, append transcript + evaluations + overall score; append guidelines; trim to last `MAX_CONTEXT_CHARS`.  
**Why:** Post coach needs full memory; prep coach stays focused; prompts stay bounded.  
**Say this:** “Same builder, two scopes — include_interview is the switch.”

### `_history_text(history)`

Last N turns as `ROLE: content` lines.

---

## `prep_coach_reply` / `post_coach_reply`

Thin wrappers around `_reply` with different **persona** strings (prep vs performance).

---

## `_reply(message, context, history, persona, llm)`

**What:**

1. Empty message → prompt to ask a question  
2. `validate_interview_answer` on user message — refuse injection/oversize  
3. If llm: persona + context + history + question  
4. Else / empty: `_fallback_reply` (keyword-routed honest advice)  
5. `validate_coaching_reply` → warnings  
6. Return `(answer, warnings)` — never raises  

**Say this:** “Input and output guardrails on every chat turn.”

### `_fallback_reply`

Deterministic guidance for gap / score / resume keywords, else generic prep-plan advice.

---

## How it connects

`callbacks_interview._render_prep_chat` / `_render_post_chat` + SQLite `chat_messages`.
