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

## Scope guardrail (prep channel only)

`SCOPE_KEYWORDS` maps the three allowed topics to keyword tuples: `resume`,
`job_description`, `interview_prep`. `detect_scope(message)` normalizes the text
(lowercase, accent stripping, whitespace collapse) and returns the first matching
scope or `None`.

**Why it is tolerant:** candidates type quickly. Matching is token-based, not raw
substring, so `"technical"` does not match inside `"technically"`. Words of 7+
characters also accept **one edit** (substitution, insertion, deletion, or adjacent
transposition) plus simple plural/gerund variants — so a slip like `"preperation"`
or `"intreview"` still lands in `interview_prep` instead of being redirected.
Multi-word phrases such as `"walk through"` match as normalized substrings.

**Say this:** “Scope is a cheap deterministic gate — no LLM call — and it forgives
typos so a real question never gets bounced to the redirect.”

When the message is out of scope, `_reply` returns `SCOPE_REDIRECT` without calling
the LLM. The post-interview coach passes no `scope_redirect`, so it answers any
performance question.

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
