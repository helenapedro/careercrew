"""Shared document-access logic (single source of truth).

This module is the one place where input is turned into plain text, whether it
arrived as an uploaded file, as pasted text, or from a URL:

- ``read_resume`` reads a PDF / DOCX / TXT file confined to the uploads folder.
- ``read_resume_text`` normalizes pasted resume text into the same clean form.
- ``fetch_job_description`` returns pasted JD text, or fetches an https URL and
  raises a clear error when the page cannot be directly accessed.
- ``query_answer_bank`` returns verified screening facts (or ``found: false``).

The same logic backs the CrewAI tools, the FastMCP server, and the stdio MCP
client, so the three paths can never diverge.

Tool guardrails live here, next to the code they protect:
- read_resume is confined to the uploads folder (no path traversal)
- fetch_job_description only fetches https URLs, with a timeout and a byte cap,
  and refuses non-HTML bodies instead of returning junk
"""

from __future__ import annotations

import os
import re
import urllib.error
import urllib.request

from careercrew.config import ANSWER_BANK_PATH, get_settings

FETCH_TIMEOUT_S = 20
MAX_FETCH_BYTES = 500_000
MAX_RESUME_CHARS = 100_000
MAX_JOB_DESCRIPTION_CHARS = 100_000
RESUME_EXTENSIONS = {".pdf", ".docx", ".txt"}

# Content types we can meaningfully turn into JD text.
_HTML_CONTENT_TYPES = {
    "text/html",
    "application/xhtml+xml",
    "application/xml",
    "text/xml",
}
_TEXT_CONTENT_TYPES = {"text/plain", "text/markdown", "text/x-markdown"}


def _upload_dir() -> str:
    return get_settings().upload_dir


class JobDescriptionError(ValueError):
    """Raised when a JD URL cannot be directly accessed.

    Carries a human-readable, user-facing message so the UI can show it in the
    error box instead of crashing the run.
    """


# --------------------------------------------------------------------------- #
# Resume input: file (PDF / DOCX / TXT) or pasted text
# --------------------------------------------------------------------------- #
def _clean_text(text: str) -> str:
    """Collapse whitespace so file and pasted input normalize identically."""
    return re.sub(r"\s+", " ", text or "").strip()


def _safe_resume_path(path: str) -> str:
    """Resolve path inside the uploads folder; reject anything else.

    Any directory component (``../``, ``a/b``, absolute paths) is rejected
    outright: only a bare file name inside the uploads folder is allowed.
    """
    candidate = (path or "").strip()
    if not candidate or candidate != os.path.basename(candidate):
        raise ValueError("resume path must be a bare file name inside the uploads folder")
    base = os.path.abspath(_upload_dir())
    full = os.path.abspath(os.path.join(base, candidate))
    if not full.startswith(base + os.sep):
        raise ValueError("resume path escapes the uploads folder")
    if not os.path.isfile(full):
        raise FileNotFoundError(f"resume not found: {candidate}")
    return full


def _read_pdf(full_path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(full_path)
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _read_docx(full_path: str) -> str:
    import docx

    document = docx.Document(full_path)
    parts = [paragraph.text for paragraph in document.paragraphs]
    # Tables often hold skills/dates in resumes; keep their cell text too.
    for table in document.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


def extract_text(full_path: str) -> str:
    """Extract text from a resume file: PDF, DOCX, or TXT."""
    lower = full_path.lower()
    if lower.endswith(".pdf"):
        raw = _read_pdf(full_path)
    elif lower.endswith(".docx"):
        raw = _read_docx(full_path)
    else:
        with open(full_path, encoding="utf-8", errors="replace") as handle:
            raw = handle.read()
    return _clean_text(raw)[:MAX_RESUME_CHARS]


def read_resume(path: str) -> str:
    """Read a resume file (PDF, DOCX, or TXT) and return its text.

    The path is confined to the uploads folder; anything else is rejected.
    """
    return extract_text(_safe_resume_path(path))


def read_resume_text(text: str) -> str:
    """Normalize pasted resume text into the same clean form as a file read."""
    cleaned = _clean_text(text)
    if not cleaned:
        raise ValueError("pasted resume text is empty")
    return cleaned[:MAX_RESUME_CHARS]


# --------------------------------------------------------------------------- #
# Job description input: pasted text or an https URL
# --------------------------------------------------------------------------- #
def _looks_like_url(source: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", source))


def _strip_html(raw_html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", raw_html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return _clean_text(text)


#: Job boards that block automated access / require login — tell the user early.
_BLOCKED_JD_HOSTS = (
    "linkedin.com",
    "www.linkedin.com",
    "indeed.com",
    "www.indeed.com",
    "glassdoor.com",
    "www.glassdoor.com",
)


def _host_of(url: str) -> str:
    try:
        from urllib.parse import urlparse

        return (urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return ""


def _fetch_url(source: str) -> str:
    """Fetch a JD from an https URL, raising JobDescriptionError when the page
    cannot be directly accessed (never returns partial or junk text)."""
    if not source.lower().startswith("https://"):
        raise JobDescriptionError(
            "Only https:// URLs are supported for job descriptions. "
            "Paste the job description text instead."
        )

    host = _host_of(source)
    if any(host == blocked or host.endswith("." + blocked) for blocked in _BLOCKED_JD_HOSTS):
        raise JobDescriptionError(
            f"{host} blocks automated access (login wall). "
            "Open the posting in your browser, copy the job description text, "
            "and paste it in the Paste posting tab instead."
        )

    request = urllib.request.Request(
        source, headers={"User-Agent": "CareerCrew/0.1 (course project)"}
    )
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_S) as response:
            content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if content_type and not (
                content_type in _HTML_CONTENT_TYPES or content_type in _TEXT_CONTENT_TYPES
            ):
                raise JobDescriptionError(
                    f"The URL serves '{content_type}', which cannot be read as a job "
                    "description (for example a direct PDF or file link). "
                    "Paste the job description text instead."
                )
            raw = response.read(MAX_FETCH_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise JobDescriptionError(
            f"The job description URL returned HTTP {exc.code}. "
            "It may require a login or block automated access; paste the text instead."
        ) from exc
    except urllib.error.URLError as exc:
        raise JobDescriptionError(
            f"The job description URL could not be reached ({exc.reason}). "
            "Check the address or paste the text instead."
        ) from exc
    except TimeoutError as exc:
        raise JobDescriptionError(
            "The job description URL timed out. Paste the text instead."
        ) from exc

    if len(raw) > MAX_FETCH_BYTES:
        raise JobDescriptionError(
            "The job description page exceeds the size limit. Paste the text instead."
        )

    decoded = raw.decode("utf-8", errors="replace")
    if content_type in _TEXT_CONTENT_TYPES:
        text = _clean_text(decoded)
    else:
        text = _strip_html(decoded)
    if not text:
        raise JobDescriptionError(
            "The job description page had no readable text (it may be a "
            "JavaScript-only page). Paste the text instead."
        )
    return text[:MAX_JOB_DESCRIPTION_CHARS]


def fetch_job_description(source: str) -> str:
    """Return JD text from an https URL or from pasted text.

    A non-URL string is treated as pasted JD text. A URL that cannot be directly
    accessed raises :class:`JobDescriptionError` with a clear message.
    """
    source = (source or "").strip()
    if not source:
        raise JobDescriptionError("No job description was provided.")
    if _looks_like_url(source):
        return _fetch_url(source)
    return _clean_text(source)[:MAX_JOB_DESCRIPTION_CHARS]


# --------------------------------------------------------------------------- #
# Verified answer bank
# --------------------------------------------------------------------------- #
_BANK_CACHE: list[dict] | None = None

# Common words that should never, on their own, match a screening question.
_STOPWORDS = {
    "are", "you", "the", "and", "for", "what", "your", "have", "has", "with",
    "this", "that", "from", "will", "would", "can", "could", "any", "you're",
    "youre", "currently", "current", "based", "where", "when", "how", "does",
    "did", "into", "out", "our", "their", "them", "they", "his", "her",
}


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 2 and token not in _STOPWORDS
    }


def _load_answer_bank() -> list[dict]:
    """Load the YAML answer bank (cached per process)."""
    global _BANK_CACHE  # noqa: PLW0603 - simple process-wide cache
    if _BANK_CACHE is None:
        import yaml

        with open(ANSWER_BANK_PATH, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        _BANK_CACHE = list(data.get("answers") or [])
    return _BANK_CACHE


def reset_answer_bank_cache() -> None:
    """Clear the answer-bank cache (used by tests that swap the file)."""
    global _BANK_CACHE  # noqa: PLW0603
    _BANK_CACHE = None


def query_answer_bank(question: str) -> dict:
    """Return the verified answer for a screening question, if one exists.

    Only entries with ``verified: true`` are ever returned. Unknown or
    unverified questions return ``found: false`` so the caller routes them to
    ``do_not_claim`` instead of inventing a fact.
    """
    question = (question or "").strip()
    if not question:
        return {"status": "error", "found": False, "error": "empty question"}

    try:
        entries = _load_answer_bank()
    except FileNotFoundError:
        return {"status": "error", "found": False, "error": "answer bank not found"}
    except Exception as exc:  # noqa: BLE001 - never crash the tool
        return {"status": "error", "found": False, "error": f"answer bank unreadable: {exc}"}

    question_tokens = _tokenize(question)
    best: dict | None = None
    best_score = 0
    for entry in entries:
        if not entry.get("verified"):
            continue
        labels = [str(entry.get("key", ""))] + [str(label) for label in entry.get("labels", [])]
        tokens: set[str] = set()
        for label in labels:
            tokens |= _tokenize(label)
        overlap = len(question_tokens & tokens)
        # A label phrase appearing verbatim is a strong signal.
        phrase_hit = any(
            label and label.lower() in question.lower() for label in labels if len(label) > 3
        )
        score = overlap + (2 if phrase_hit else 0)
        if score > best_score:
            best_score = score
            best = entry

    # Require a real signal (an overlapping keyword or a verbatim label); a
    # single accidental stopword match must not answer an unrelated question.
    if best is None or best_score < 1:
        return {
            "status": "not_found",
            "found": False,
            "question": question,
            "reason": "no verified answer-bank entry matches this question",
        }

    return {
        "status": "ok",
        "found": True,
        "question": question,
        "key": best.get("key"),
        "answer": best.get("answer"),
        "source": "answer_bank",
    }
