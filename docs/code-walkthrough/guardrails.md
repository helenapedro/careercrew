# Walkthrough: `careercrew/guardrails.py`

**File purpose:** Input, output, and interactive-path checks. Keyword filters alone are not “safety”; structural checks (citations, answer_bank source, share totals) are.

**Tool confinement** (uploads folder) lives next to the tools in `document_tools.py`, not only here.

---

## Constants

| Symbol | Meaning |
|--------|---------|
| `EMAIL_RE` / `PHONE_RE` | PII patterns for redaction |
| `ALLOWED_EXTENSIONS` | `.pdf`, `.docx`, `.txt` |
| `MAX_UPLOAD_BYTES` | 5 MB |
| `MIN_PASTED_RESUME_CHARS` | 40 |
| `MAX_JD_CHARS` | 100_000 |
| `_DISALLOWED_INPUT` | Injection-ish phrases (ignore previous instructions, rm -rf, etc.) |

---

## Input helpers

### `redact_pii(text)`

**What:** Replace emails/phones with `[redacted …]`.  
**Why:** Reduce PII before LLM calls when pasted text is used.  
**Say this:** “We scrub contact info before it hits the model.”

### `check_upload(path)`

**What:** Must be a file; extension allowed; size ≤ 5 MB; else `ValueError`.  
**I/O:** `os.path` / `getsize`.

### `InputValidationResult`

`ok` + `errors` list.

### `validate_request(...)` — **Analyze gate**

**What (branches):**

- Resume: exactly one of file / paste; paste long enough; file extension OK  
- JD: exactly one of file / paste; extension OK; paste length; injection pattern on JD text  
- Screening questions: each line checked against `_DISALLOWED_INPUT`  

**Why:** Refuse ambiguous or malicious input before the crew.  
**Say this:** “One resume source, one JD source — never both, never neither.”

---

## Output / interactive validators

### `OutputValidationResult`

`ok`, `errors`, `warnings`.

### `validate_citations(feedback_draft, profile)`

**What:** Every `cited_fact` must share meaningful tokens with profile text (skills/achievements); empty cite → error.  
**Why:** Rewrites must not invent experience.  
**Say this:** “No bullet without a resume fingerprint.”

### `validate_prep_plan(plan, gaps, requirements)`

**What:** Priorities in {high,medium,low}; evidence must relate to real gap/requirement text; `suggested_share_pct` sum ≈ 100.  
**Why:** Prep advice stays grounded; returns **list of problems** (pipeline treats as warnings).

### `validate_interview_answer(answer, max_chars=6000)`

**What:** Non-empty, length cap, injection pattern.  
**Used by:** Mock interview submit + coach chat input.

### `validate_evaluation(evaluation)`

**What:** Score in 0..100; improvements non-empty; reject fabricated-experience patterns in model text when possible.  
**Why:** Per-question feedback stays actionable and honest.

### `validate_transcript_turn(turn)`

**What:** Role valid; text non-empty.  
**Why:** Transcript integrity.

### `validate_coaching_reply(reply, context_text="")`

**What:** Non-empty; refuse replies that claim facts absent from context / leak PII patterns; safe-boundary refusals OK.  
**Why:** Coaches must not invent resume facts.

### `validate_package(package, feedback=None, profile=None)` — **fail closed**

**What:**

- Every screening answer: `source == "answer_bank"` and verified  
- Optionally run citation checks on feedback/profile  
- Build `OutputValidationResult`  

**Why:** Package must never ship invented screening facts.  
**Say this:** “If validation fails, Analyze raises — we do not hand a bad package to HITL.”

---

## How it connects

- **Input:** `pipeline.run_analysis` start  
- **Output package/prep:** end of `run_analysis`  
- **Interview/coach:** `app.py` handlers + `coach._reply` / `interview` path  
