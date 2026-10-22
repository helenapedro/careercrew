# Walkthrough: `careercrew/llm.py`

**File purpose:** Optional OpenAI chat callable for interview / prep / coach modules. Keeps those modules testable (`llm=None` → deterministic path).

---

## `available()`

`settings.has_llm`.

## `_client()`

Same pattern as `audio._client`, plus a **90 s timeout** and a single retry. These callbacks run inside the Gradio queue, so an unbounded HTTP call would leave a tab spinning on "processing" forever instead of falling back.

---

## `chat_completion(prompt, system="", temperature=0.3)`

**What:** Build messages; call `chat.completions.create` with `settings.openai_model`; return content or `""` on failure / no key.  
**Why never raise:** Callers must fall back.  
**I/O:** OpenAI HTTPS.

**Temperature handling:** Reasoning-style models (e.g. `gpt-6-luna`) reject `temperature` with a 400 `unsupported_value`. The helper sends it only when the model is known to accept it; on the first rejection it drops the knob, retries once, and records the model in `_NO_TEMPERATURE_MODELS` so later calls skip the doomed attempt. Without this, every prep-coach, mock-interview, and post-coach call fails closed to the offline fallback.

**Say this:** "Some models don't accept a temperature setting, so we adapt per model instead of hard-coding one."

---

## `callable_or_none()`

Returns `chat_completion` if key set, else `None` — what `app.py` passes into interview/coach.

**Say this:** “If this returns None, every interactive agent still works offline.”
