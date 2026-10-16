# Code path: Prep coach and Post-interview coach

Two full-memory chat windows. Same context builder; post-interview channel
adds the mock interview transcript, evaluations, and score.

**Prerequisite:** Analyze (`ctx_state`). Post-interview coach is most useful
after a completed mock interview (`iv_state`).  
**UI tabs:** **Prep coach**, **Post-interview coach**.

---

## 1. Modules

| Module | Role |
|--------|------|
| [`app.py`](../app.py) `_render_prep_chat`, `_render_post_chat` | Gradio Chatbot + textbox submit |
| [`careercrew/coach.py`](../careercrew/coach.py) | `build_context`, `prep_coach_reply`, `post_coach_reply` |
| [`careercrew/llm.py`](../careercrew/llm.py) | `chat_completion` / `callable_or_none` |
| [`careercrew/guardrails.py`](../careercrew/guardrails.py) | Input size/injection; `validate_coaching_reply` |
| [`careercrew/session_store.py`](../careercrew/session_store.py) | `chat_messages` table |
| Knowledge | `interview_guidelines.md` (via `COACHING_GUIDELINES_PATH`) |

---

## 2. Context assembly (`build_context`)

| Slice | Always? | Source |
|-------|---------|--------|
| Candidate profile JSON | If present | Analyze |
| Job requirements JSON | If present | Analyze |
| Gap report JSON | If present | Analyze |
| Interview prep plan JSON | If present | Analyze / fallback |
| Mock transcript + evals + overall score | Only if `include_interview=True` | Mock session |
| Coaching guidelines markdown | If file readable | `knowledge/interview_guidelines.md` |

Bounded to **`MAX_CONTEXT_CHARS` (12_000)** — trims from the front, keeps the tail (recent material).

| Channel | `include_interview` |
|---------|---------------------|
| Prep coach | **False** (resume + prep focus) |
| Post-interview coach | **True** (full memory) |

---

## 3. Prep coach turn (`_render_prep_chat`)

| # | Step | Code | I/O |
|---|------|------|-----|
| 1 | Load Analyze models | `_context_models(ctx_state)` | Memory |
| 2 | Build context | `coach.build_context(profile, requirements, gaps, prep_plan)` | Memory |
| 3 | Call coach | `prep_coach_reply(message, context, history, llm=...)` | Optional OpenAI |
| 4 | Persist messages | `_STORE.add_chat_message(session_id, channel="prep", ...)` | SQLite |
| 5 | Update chatbot | Append user + assistant messages | UI |

Persona (system): resume improvement + interview prep; never invent experience.

---

## 4. Post-interview coach turn (`_render_post_chat`)

Same shape, plus:

| Extra | Detail |
|-------|--------|
| Load mock session | `_load_interview(iv_state)` |
| Context | `build_context(..., interview=session, include_interview=True)` |
| Entry | `post_coach_reply(...)` |
| Channel | `channel="post"` in SQLite |

Persona: answer any follow-up using JD, resume, gaps, prep plan, **full transcript**, per-question evals, overall score.

---

## 5. Reply pipeline (`coach._reply`)

| # | Step | Why |
|---|------|-----|
| 1 | Strip empty message | Prompt for a question |
| 2 | `validate_interview_answer(message, max_chars=4000)` | Untrusted user input |
| 3 | Build prompt: persona + context + last `MAX_HISTORY_TURNS` (12) + user message | Bounded memory |
| 4 | If LLM callable → `llm(prompt)`; else `_fallback_reply` | Works without API key |
| 5 | `validate_coaching_reply(reply, context_text=...)` | No invented facts / PII leakage style checks; fail → safe refusal string |
| 6 | Return `(reply, warnings)` | Never raises into Gradio |

---

## 6. SQLite `chat_messages`

| Column | Meaning |
|--------|---------|
| `session_id` | Usually Analyze `package_id` (or `"session"`) |
| `channel` | `prep` or `post` |
| `role` | `user` / `assistant` |
| `content` | Message text |
| `created_at` | UTC ISO |

Survives app restarts; Gradio `history` also carries the live thread.

---

## 7. Talking points

- Two windows on purpose: prep vs post-interview have different context scopes  
- Full memory ≠ unbounded: character cap + history turn cap  
- Guardrails on both input and output  
- Deterministic fallback still cites what is in context when there is no LLM  
