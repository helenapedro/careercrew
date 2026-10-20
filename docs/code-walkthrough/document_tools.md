# Walkthrough: `careercrew/document_tools.py`

**File purpose:** Single source of truth for turning uploads/paste into text and for verified screening answers. Used by MCP server, pipeline fail-fast, and (historically) any local wrappers.

**Say this:** “One implementation — MCP, pipeline, and tools cannot drift.”

---

## Constants / errors

| Symbol | Meaning |
|--------|---------|
| `MAX_RESUME_CHARS` / `MAX_JOB_DESCRIPTION_CHARS` | Cap extracted text at 100k |
| `RESUME_EXTENSIONS` | `.pdf`, `.docx`, `.txt` |
| `JobDescriptionError` | User-facing JD failures (URL rejected, empty file, etc.) |

---

## Path confinement (tool guardrail)

### `_upload_dir()`

Reads `settings.upload_dir`.

### `_safe_upload_path(path, kind)`

**What:** Reject empty / paths with directories / `../`; join under uploads; `abspath` must stay under base; must be a real file.  
**Why:** Agents cannot read arbitrary disk paths.  
**Say this:** “Bare filename only inside uploads — classic path-traversal defense.”

---

## Text extraction

### `_clean_text(text)`

Collapse whitespace so file and paste look the same.

### `_read_pdf` / `_read_docx`

Lazy-import `pypdf` / `python-docx`; DOCX also walks tables (skills often live there).

### `extract_text(full_path)`

Branch on extension → clean → truncate.

### `read_resume(path)` / `read_resume_text(text)`

File via safe path; paste must be non-empty.

---

## Job description

### `_looks_like_url(source)`

Scheme:// prefix.

### `read_job_description(source)`

**Branches:**

1. Empty → `JobDescriptionError`  
2. URL → reject with “download or paste” message (no scraping)  
3. Bare name with supported extension → try uploads read; if missing file, treat as paste text  
4. Else treat as pasted JD text  

**Say this:** “We dropped JD URL fetch because job boards block it.”

### `_has_supported_extension(name)`

Helper for the bare-filename branch.

---

## Answer bank

### `_tokenize` / `_STOPWORDS`

Tokenize for matching; ignore common words so “are you” alone cannot match.

### `_load_answer_bank()` / `reset_answer_bank_cache()`

Load YAML once into `_BANK_CACHE`; tests can reset.

### `query_answer_bank(question)`

**What:**

1. Empty → error payload  
2. Load bank; skip entries without `verified: true`  
3. Score overlap of question tokens vs entry key/labels (+ bonus for phrase hit)  
4. Best score < 1 → `found: false`  
5. Else return `found: true`, `answer`, `source: answer_bank`  

**Why:** Unknown questions become `do_not_claim`, never invented facts.  
**I/O:** Read `data/answer_bank.yaml`.  
**Say this:** “Only verified bank rows can answer screening questions.”

---

## How it connects

- MCP server thin-wraps these three functions  
- Pipeline calls resume/JD helpers before the crew  
- Fallback calls `query_answer_bank` via MCP client (same logic)
