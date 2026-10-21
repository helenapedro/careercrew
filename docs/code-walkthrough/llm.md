# Walkthrough: `careercrew/llm.py`

**File purpose:** Optional OpenAI chat callable for interview / prep / coach modules. Keeps those modules testable (`llm=None` → deterministic path).

---

## `available()`

`settings.has_llm`.

## `_client()`

Same pattern as `audio._client`.

---

## `chat_completion(prompt, system="", temperature=0.3)`

**What:** Build messages; call `chat.completions.create` with `settings.openai_model`; return content or `""` on failure / no key.  
**Why never raise:** Callers must fall back.  
**I/O:** OpenAI HTTPS.

---

## `callable_or_none()`

Returns `chat_completion` if key set, else `None` — what `app.py` passes into interview/coach.

**Say this:** “If this returns None, every interactive agent still works offline.”
