## 1. Setup and Reproduction

Verified against the `dev` branch. Prerequisites: Python 3.11 to 3.12, git.

### Install

```bash
git clone https://github.com/helenapedro/careercrew.git
cd careercrew
git checkout dev
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

For the test suite:

```bash
pip install -r requirements-dev.txt
pytest -q
```

### Configuration

```bash
cp .env.example .env   # then put your OPENAI_API_KEY in .env
```

Key variables (see `.env.example` for the full list):

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | No | Full agent crew and voice interview. Without it the crew is skipped and a deterministic gap-based prep plan is used; the UI banner says so |
| `CAREERCREW_UPLOAD_DIR` | No | Folder for resume/JD uploads (created automatically) |
| `CAREERCREW_DB_PATH` | No | SQLite database for review history, interviews, and chats |
| `CAREERCREW_MAX_REVISIONS` | No | Bounded revision limit for the HITL review loop (default 2) |
| `CAREERCREW_STT_MODEL` / `CAREERCREW_TTS_MODEL` | No | Mock-interview audio models (defaults: whisper-1 / tts-1) |

### Run

CLI on the fictional samples:

```bash
python main.py --resume samples/sample_resume.txt --jd samples/sample_jd.txt
```

Seniority for the prep plan is inferred from the JD. Optional CLI override:
`--seniority "5-10 years"`.

Web UI:

```bash
python app.py
```

MCP server standalone (manual smoke test):

```bash
python -m mcp_server.server
```

### Input rules (enforced by input guardrails)

- **Resume**: upload a `.pdf`, `.docx`, or `.txt` file **or** paste the resume text. Provide exactly one source.
- **Job description**: upload a file or paste the text. URLs are rejected with a clear error (job boards block direct reads).

### Notes for reproduction

- The test suite is offline: the MCP fallback path needs no API key (`tests/conftest.py` points the database and upload dir at temp locations).
- `pyproject.toml` defines a `live` marker for opt-in tests that would call real external providers; no test currently uses it.
- Voice features degrade to text when no audio-capable API key is configured; the UI states this explicitly.
