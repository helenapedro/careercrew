# Walkthrough: `careercrew/document_tools.py`

**File purpose:** Single source of truth for turning an upload or pasted text into plain text. Used by the MCP server and by the pipeline's fail-fast read.

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

### `_has_supported_extension(name)`

Helper for the bare-filename branch.

---

## How it connects

- MCP server thin-wraps the two read functions
- Pipeline calls resume/JD helpers before the crew (fail-fast validation)
- Crew agents call the same functions through MCP
