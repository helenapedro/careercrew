"""CareerCrew - input, tool, and output guardrails.

Guardrails are the safety and integrity checks around the whole workflow:

* **Input**  - validate the resume/JD inputs, redact PII, and bound sizes.
* **Tool**   - confined uploads folder, https-only fetch (in ``document_tools``).
* **Output** - prove the package is honestly grounded: every bullet cites a
  real profile fact and every screening answer came from the answer bank. Fail
  closed: if the package cannot be validated, it is not handed to the human.

A keyword filter alone is *not* treated as a guarantee of safety; the real
protections are the structural and reference checks below.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from careercrew.models import (
    ApplicationPackage,
    CandidateProfile,
    FeedbackDraft,
)

# --------------------------------------------------------------------------- #
# Input guardrails
# --------------------------------------------------------------------------- #
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MIN_PASTED_RESUME_CHARS = 40
MAX_JD_CHARS = 100_000

#: Patterns we refuse outright (tool/instruction injection in user input).
_DISALLOWED_INPUT = re.compile(
    r"(ignore (all )?previous instructions|disregard .*guidelines|"
    r"execute (this )?(code|command)|rm -rf|drop table)",
    re.IGNORECASE,
)


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


@dataclass
class InputValidationResult:
    """Outcome of validating a raw analysis request."""

    ok: bool
    errors: list[str] = field(default_factory=list)


def validate_request(
    *,
    resume_path: str | None = None,
    resume_text: str | None = None,
    jd_source: str = "",
    screening_questions: list[str] | None = None,
) -> InputValidationResult:
    """Validate the resume and JD inputs before any work begins.

    Requires exactly one resume source (file OR pasted text, not both) and a
    non-empty job description.
    """
    errors: list[str] = []

    has_file = bool(resume_path)
    has_text = bool((resume_text or "").strip())
    if has_file and has_text:
        errors.append("Provide either an uploaded resume file or pasted resume text, not both.")
    elif not has_file and not has_text:
        errors.append("Provide a resume: upload a file (PDF/DOCX/TXT) or paste the text.")
    elif has_text and len((resume_text or "").strip()) < MIN_PASTED_RESUME_CHARS:
        errors.append(
            f"Pasted resume text is too short (min {MIN_PASTED_RESUME_CHARS} characters)."
        )
    elif has_file:
        ext = os.path.splitext((resume_path or "").lower())[1]
        if ext not in ALLOWED_EXTENSIONS:
            errors.append(f"Unsupported resume file type: {ext or '(none)'}.")

    jd = (jd_source or "").strip()
    if not jd:
        errors.append("Provide a job description (paste text or an https URL).")
    elif len(jd) > MAX_JD_CHARS:
        errors.append("The job description is too long.")
    elif _DISALLOWED_INPUT.search(jd):
        errors.append("The job description contains a disallowed instruction pattern.")

    if (resume_text or "").strip() and _DISALLOWED_INPUT.search(resume_text or ""):
        errors.append("The resume text contains a disallowed instruction pattern.")

    return InputValidationResult(ok=not errors, errors=errors)


# --------------------------------------------------------------------------- #
# Output guardrails
# --------------------------------------------------------------------------- #
@dataclass
class OutputValidationResult:
    """Outcome of validating a draft package before human review."""

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_citations(feedback_draft: FeedbackDraft, profile: CandidateProfile) -> list[str]:
    """Verify every rewritten bullet cites a real profile fact.

    Strict: a bullet with no citation (or a citation whose key content is
    absent from the serialized profile) fails closed. Returns problem strings;
    empty means the draft passed.
    """
    problems: list[str] = []
    profile_text = profile.model_dump_json().lower()

    def _significant_tokens(text: str) -> list[str]:
        return [tok for tok in re.findall(r"[a-z0-9]+", text.lower()) if len(tok) > 3]

    for index, bullet in enumerate(feedback_draft.rewritten_bullets):
        if not bullet.cited_fact.strip():
            problems.append(f"bullet {index} has no cited fact")
            continue
        tokens = _significant_tokens(bullet.cited_fact)
        # Require at least one significant token from the citation to appear in
        # the profile, otherwise the citation is not traceable to a real fact.
        if tokens and not any(tok in profile_text for tok in tokens):
            problems.append(f"bullet {index} cites a fact not found in the profile")
    return problems


def validate_package(
    package: ApplicationPackage,
    feedback_draft: FeedbackDraft | None = None,
    profile: CandidateProfile | None = None,
) -> OutputValidationResult:
    """Prove the package is honestly grounded. Fail closed.

    Rules:
    - Every screening answer must have ``source == "answer_bank"`` and a
      non-empty answer; no invented screening facts are allowed.
    - Every rewritten bullet (when feedback is supplied) must cite a profile
      fact (see :func:`validate_citations`).
    - A package with no content at all is an error, not a silent pass.
    """
    errors: list[str] = []
    warnings: list[str] = []

    for index, answer in enumerate(package.screening_answers):
        if answer.source != "answer_bank":
            errors.append(
                f"screening answer {index} has source '{answer.source}', "
                "but only 'answer_bank' is allowed"
            )
        if not answer.answer.strip():
            errors.append(f"screening answer {index} is empty")

    if feedback_draft is not None and profile is not None:
        for problem in validate_citations(feedback_draft, profile):
            errors.append(problem)

    if not package.screening_answers and not package.package_summary.strip():
        errors.append("The package contains no screening answers and no summary.")

    if package.do_not_claim:
        warnings.append(
            f"{len(package.do_not_claim)} item(s) are listed under do_not_claim and need "
            "the candidate's input."
        )

    return OutputValidationResult(ok=not errors, errors=errors, warnings=warnings)
