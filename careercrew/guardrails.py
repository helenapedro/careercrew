"""Checks that run before and after the crew so invented claims never ship.

What it does: validates inputs, citations, and the prep plan.
Who calls it: the pipeline, the interview callbacks, and the coaching callbacks.
What it returns: a pass/fail result, or a list of problems. Fail closed.
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
    jd_path: str | None = None,
    jd_text: str | None = None,
) -> InputValidationResult:
    """Validate the resume and JD inputs before any work begins.

    Requires exactly one resume source (file OR pasted text, not both) and
    exactly one job-description source (uploaded file OR pasted text).
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

    jd_file = bool(jd_path)
    jd_pasted = bool((jd_text or "").strip())
    if jd_file and jd_pasted:
        errors.append(
            "Provide either an uploaded job description file or pasted job description "
            "text, not both."
        )
    elif not jd_file and not jd_pasted:
        errors.append(
            "Provide a job description: upload a file (PDF/DOCX/TXT) or paste the text."
        )
    elif jd_file:
        ext = os.path.splitext((jd_path or "").lower())[1]
        if ext not in ALLOWED_EXTENSIONS:
            errors.append(f"Unsupported job description file type: {ext or '(none)'}.")
    elif len((jd_text or "").strip()) > MAX_JD_CHARS:
        errors.append("The job description is too long.")
    elif _DISALLOWED_INPUT.search(jd_text or ""):
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


def validate_prep_plan(plan, gaps, requirements=None) -> list[str]:
    """Verify the Interview Prep Advisor stayed grounded.

    Rules:
    - Every focus area must cite a real requirement (matching a gap verdict or
      a job requirement). This is returned as a warning-level problem, not a
      hard failure, so the user still gets the plan.
    - ``priority`` must be one of high/medium/low.
    - Suggested shares should total roughly 100 when there is more than one area.
    """
    problems: list[str] = []
    if plan is None:
        return ["no interview prep plan was produced"]

    requirement_text = " ".join(
        f"{verdict.requirement} {verdict.supporting_fact}".lower()
        for verdict in getattr(gaps, "verdicts", [])
    )
    if requirements is not None:
        requirement_text += " " + requirements.model_dump_json().lower()

    for index, focus in enumerate(plan.focus_areas):
        if (focus.priority or "").lower() not in {"high", "medium", "low"}:
            problems.append(f"prep focus {index} has an invalid priority '{focus.priority}'")
        tokens = [tok for tok in re.findall(r"[a-z0-9]+", (focus.evidence or "").lower()) if len(tok) > 3]
        if not tokens:
            problems.append(f"prep focus {index} has no grounded evidence")
        elif requirement_text and not any(tok in requirement_text for tok in tokens):
            problems.append(
                f"prep focus {index} cites evidence not found in the requirements"
            )

    if len(plan.focus_areas) > 1:
        total = sum(focus.suggested_share_pct for focus in plan.focus_areas)
        if total and not (80 <= total <= 120):
            problems.append(
                f"prep focus shares total {total}%, which is far from the expected ~100%"
            )
    return problems


def validate_interview_answer(answer: str, *, max_chars: int = 6000) -> list[str]:
    """Validate a candidate's interview answer before it reaches any agent.

    Rejects empty, oversized, or instruction-injection answers. Returns problem
    strings (empty means the answer is acceptable).
    """
    problems: list[str] = []
    text = (answer or "").strip()
    if not text:
        problems.append("the answer is empty")
        return problems
    if len(text) > max_chars:
        problems.append(f"the answer is too long (max {max_chars} characters)")
    if _DISALLOWED_INPUT.search(text):
        problems.append("the answer contains a disallowed instruction pattern")
    return problems


def validate_evaluation(evaluation, *, max_score: int = 100) -> list[str]:
    """Verify a per-answer evaluation stayed honest and bounded.

    Rules:
    - Score in range.
    - At least one concrete improvement (so feedback is actionable).
    - ``what_interviewer_wanted`` must not be empty.
    """
    problems: list[str] = []
    if evaluation is None:
        return ["no evaluation was produced"]
    if not (0 <= int(evaluation.score) <= max_score):
        problems.append(f"evaluation score {evaluation.score} is out of range")
    if not (evaluation.what_interviewer_wanted or "").strip():
        problems.append("evaluation is missing what the interviewer was looking for")
    if not evaluation.improvements:
        problems.append("evaluation has no concrete improvements")
    return problems


def validate_transcript_turn(turn) -> list[str]:
    """A transcript turn must carry text and a known speaker role."""
    problems: list[str] = []
    if turn is None:
        return ["transcript turn is missing"]
    if not (getattr(turn, "text", "") or "").strip():
        problems.append("transcript turn has no text")
    role = getattr(getattr(turn, "role", None), "value", getattr(turn, "role", None))
    if role not in {"interviewer", "candidate"}:
        problems.append(f"transcript turn has an unknown role '{role}'")
    return problems


def validate_coaching_reply(reply: str, *, context_text: str = "") -> list[str]:
    """Check a coaching chat reply for honesty and safety.

    Returns problem strings. The reply must be non-empty, must not leak PII, and
    must not invite the candidate to fabricate experience. We do not hard-block
    the reply (chat must stay usable) - callers surface problems as warnings.
    """
    problems: list[str] = []
    text = (reply or "").strip()
    if not text:
        problems.append("the coaching reply is empty")
        return problems
    if EMAIL_RE.search(text) or PHONE_RE.search(text):
        problems.append("the coaching reply appears to contain personal contact details")
    if re.search(
        r"\b(lie|fabricate|make up (?:an? )?(?:employer|title|degree|date)|"
        r"pretend you (?:have|worked))\b",
        text,
        re.IGNORECASE,
    ):
        problems.append("the coaching reply may suggest misrepresenting experience")
    return problems



def validate_package(
    package: ApplicationPackage,
    feedback_draft: FeedbackDraft | None = None,
    profile: CandidateProfile | None = None,
) -> OutputValidationResult:
    """Prove the package is honestly grounded. Fail closed.

    Rules:
    - Every rewritten bullet (when feedback is supplied) must cite a profile
      fact (see :func:`validate_citations`).
    """
    errors: list[str] = []
    warnings: list[str] = []

    if feedback_draft is not None and profile is not None:
        for problem in validate_citations(feedback_draft, profile):
            errors.append(problem)

    if package.do_not_claim:
        warnings.append(
            f"{len(package.do_not_claim)} item(s) are listed under do_not_claim and need "
            "the candidate's input."
        )

    return OutputValidationResult(ok=not errors, errors=errors, warnings=warnings)
