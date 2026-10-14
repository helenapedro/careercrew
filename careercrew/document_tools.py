"""Shared document-access logic (single source of truth).

Day 2: wrapped as CrewAI @tool functions in careercrew/tools.py so the crew
runs end to end right now.
Day 4: wrapped as MCP tools in mcp_server/server.py; crew.py then swaps the
@tool wrappers for MCP-backed tools. The logic below does not change.

Tool guardrails live here, next to the code they protect:
- read_resume is confined to the uploads folder (no path traversal)
- fetch_job_description only fetches https URLs, with a timeout and a byte cap
"""

from __future__ import annotations

import os
import re
import urllib.request

UPLOAD_DIR = os.environ.get("CAREERCREW_UPLOAD_DIR", "uploads")
FETCH_TIMEOUT_S = 20
MAX_FETCH_BYTES = 500_000
MAX_RESUME_CHARS = 100_000


def _safe_resume_path(path: str) -> str:
    """Resolve path inside the uploads folder; reject anything else."""
    base = os.path.abspath(UPLOAD_DIR)
    full = os.path.abspath(os.path.join(base, os.path.basename(path)))
    if not full.startswith(base + os.sep):
        raise ValueError("resume path escapes the uploads folder")
    if not os.path.isfile(full):
        raise FileNotFoundError(f"resume not found: {os.path.basename(path)}")
    return full


def read_resume(path: str) -> str:
    """Read a resume file (PDF or plain text) and return its text."""
    full = _safe_resume_path(path)
    if full.lower().endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(full)
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    else:
        with open(full, encoding="utf-8", errors="replace") as f:
            text = f.read()
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_RESUME_CHARS]


def fetch_job_description(source: str) -> str:
    """Return JD text. Accepts an https URL (fetched with limits) or pasted text."""
    source = (source or "").strip()
    if source.lower().startswith("https://"):
        req = urllib.request.Request(
            source, headers={"User-Agent": "CareerCrew/0.1 (course project)"}
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
            raw = resp.read(MAX_FETCH_BYTES + 1)
        if len(raw) > MAX_FETCH_BYTES:
            raise ValueError("job description page exceeds the byte limit")
        text = raw.decode("utf-8", errors="replace")
        # crude HTML strip; Day 3 can upgrade this if the team wants
        text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:MAX_RESUME_CHARS]
    # otherwise treat it as pasted JD text
    return source[:MAX_RESUME_CHARS]
