"""Guardrails (Day 3 owns the wiring; input helpers are implemented now).

Layers:
- input:  redact_pii + check_upload (implemented below; call before kickoff)
- output: validate_citations (stub: team implements the check on Day 3)
- tool:   enforced inside document_tools (https-only fetch, byte caps,
          uploads-folder confinement)
"""

from __future__ import annotations

import os
import re

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")

ALLOWED_EXTENSIONS = {".pdf", ".txt"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def redact_pii(text: str) -> str:
    """Remove emails and phone numbers before any LLM call."""
    text = EMAIL_RE.sub("[redacted email]", text)
    text = PHONE_RE.sub("[redacted phone]", text)
    return text


def check_upload(path: str) -> None:
    """Reject missing files, bad extensions, and oversized uploads."""
    if not os.path.isfile(path):
        raise ValueError(f"upload not found: {path}")
    _, ext = os.path.splitext(path.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"unsupported file type: {ext or '(none)'}")
    if os.path.getsize(path) > MAX_UPLOAD_BYTES:
        raise ValueError("file exceeds the 5 MB upload limit")


def validate_citations(feedback_draft, profile) -> list[str]:
    """TODO (Day 3): verify every rewritten bullet cites a real profile fact.

    Return a list of problem strings; empty means the draft passed.
    Suggested approach: for each bullet, check that cited_fact is non-empty
    and that its key nouns appear in the serialized profile. Keep it strict:
    a bullet with no citation fails closed.
    """
    problems: list[str] = []
    for i, bullet in enumerate(feedback_draft.rewritten_bullets):
        if not bullet.cited_fact.strip():
            problems.append(f"bullet {i} has no cited fact")
    return problems
