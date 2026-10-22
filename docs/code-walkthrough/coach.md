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

The coach answers about **this analysis**: the candidate's resume, this job
description, and preparation for this role. Two layers:

1. **Analysis anchors.** `context_anchors(profile=..., requirements=..., gaps=...,
   prep_plan=...)` collects the role-specific vocabulary from the structured
   models — required skills, keywords, seniority, gap requirements, focus areas —
   and `build_context` embeds it as `## Topics in this analysis`. Generic coaching
   prose is deliberately excluded, so words like "give" or "time" cannot make an
   unrelated question look relevant.
2. **Keyword scopes.** `SCOPE_KEYWORDS` maps `resume`, `job_description`,
   `interview_prep` to keyword tuples, matched with token/typo tolerance.

`detect_scope(message, context)` returns a scope only when the question is about
this analysis:

- a recognized off-topic domain (`OFF_TOPIC_WORDS`) is always redirected;
- an explicit prep keyword is enough on its own;
- generic learning phrasing (`GENERIC_PREP_WORDS`: "learn", "first step", ...)
  requires an anchor — the named technology must appear in this analysis;
- otherwise the question must share an anchor with the analysis.

**Why this shape:** an allowlist of preparation phrasing cannot anticipate how a
candidate words a question. "what I have to do in the first step for learn
Kubernetes?" has no prep keyword at all, yet Kubernetes *is* a requirement in this
job description — so anchoring on the analysis answers it, while "how do I bake a
cake" shares nothing and is redirected. `detect_scope` stays deterministic: no LLM
call, cheap to test.

**Say this:** “Scope is anchored to the analysis on screen, not to a fixed keyword
list, so real preparation questions in the candidate's own words get answered and
unrelated topics do not.”

When a message is rejected, `_reply` returns `SCOPE_REDIRECT` without calling the
LLM. The post-interview coach passes no `scope_redirect`, so it answers any
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
