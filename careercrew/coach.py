"""Two chats: one for prep, one for after the mock interview.

What it does: answers follow-up questions using the analysis already on screen.
Who calls it: the prep-coach and post-interview-coach send buttons.
What it returns: a reply string, plus any guardrail warnings.
"""

from __future__ import annotations

import logging
import re
import unicodedata

from careercrew import guardrails
from careercrew.config import COACHING_GUIDELINES_PATH

logger = logging.getLogger("careercrew.coach")

MAX_CONTEXT_CHARS = 12_000
MAX_HISTORY_TURNS = 12


def _guidelines() -> str:
    try:
        return COACHING_GUIDELINES_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""


def build_context(
    *,
    profile=None,
    requirements=None,
    gaps=None,
    prep_plan=None,
    interview=None,
    include_interview: bool = False,
) -> str:
    """Assemble the bounded system context shared by both chat channels.

    ``include_interview`` adds the mock interview transcript, evaluations, and
    score (used by the post-interview coach). The result is trimmed to
    ``MAX_CONTEXT_CHARS`` from the end, keeping the most recent material.
    """
    parts: list[str] = ["# CareerCrew coaching context"]

    if profile is not None:
        parts.append("## Candidate profile (from the resume)\n" + profile.model_dump_json())
    if requirements is not None:
        parts.append("## Job requirements (from the job description)\n" + requirements.model_dump_json())
    if gaps is not None:
        parts.append("## Honest gap report\n" + gaps.model_dump_json())
    if prep_plan is not None:
        parts.append("## Interview preparation plan\n" + prep_plan.model_dump_json())

    if include_interview and interview is not None:
        transcript = "\n".join(
            f"{turn.role.value.upper()}: {turn.text}" for turn in interview.turns
        )
        parts.append(f"## Mock interview transcript\n{transcript}")
        evaluations = "\n".join(
            f"Q{e.question_index + 1} score {e.score}: {e.what_interviewer_wanted} | "
            f"improve: {'; '.join(e.improvements)}"
            for e in interview.evaluations
        )
        parts.append(
            f"## Mock interview evaluations\n{evaluations}\n\n"
            f"## Overall mock interview score: {interview.overall_score}/100\n"
            f"{interview.overall_summary}"
        )

    guidelines = _guidelines()
    if guidelines:
        parts.append("## Coaching guidelines\n" + guidelines)

    context = "\n\n".join(parts)
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[-MAX_CONTEXT_CHARS:]
    return context


def _history_text(history: list[dict] | None) -> str:
    if not history:
        return "(no previous messages)"
    lines: list[str] = []
    for message in history[-MAX_HISTORY_TURNS:]:
        role = str(message.get("role", "user")).upper()
        content = str(message.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) or "(no previous messages)"


# The prep chatbot is scoped to three topics (team decision, 2026-10-16):
# the candidate's resume, the job description, and interview preparation.
# Questions outside these scopes get a deterministic redirect instead of an answer.
SCOPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "resume": (
        "resume", "cv", "bullet", "rewrite", "experience", "skill",
        "background", "job title", "employment", "internship", "career",
    ),
    "job_description": (
        "job description", "jd", "posting", "requirement", "role",
        "responsibilities", "qualification", "mean by", "company",
    ),
    "interview_prep": (
        "interview", "prep", "prepare", "preparation", "study", "readiness",
        "practice", "mock", "question", "nervous", "tips", "advice", "star",
        "behavioral", "tell me about", "walk through", "gap", "weakness",
        "strength", "technical", "coding", "whiteboard", "rehearse",
        "get ready", "brush up",
    ),
}

SCOPE_REDIRECT = (
    "I can help with three things: your resume, the job description, "
    "or interview preparation. Could you ask about one of those?"
)

# Scope matching is deliberately tolerant: candidates type quickly and misspell
# words ("preperation", "intreview"). Multi-word phrases match as normalized
# substrings; single words match whole tokens, and words of 7+ characters also
# tolerate a single typo (one substitution, insertion, deletion, or swap) so a
# misspelling does not push an in-scope question into the redirect.
_FUZZY_MIN_KEYWORD_CHARS = 7
_WORD_RE = re.compile(r"[a-z0-9+#]+")


def _normalize(message: str) -> str:
    text = unicodedata.normalize("NFKD", (message or "").lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.split())


def _within_one_typo(token: str, keyword: str) -> bool:
    """True when ``token`` is ``keyword`` with at most one edit.

    Counts a single substitution, insertion, deletion, or adjacent transposition,
    which covers the common slips ("preperation", "intreview") without matching
    words that merely share a stem ("technical" vs "technically").
    """
    if len(keyword) < _FUZZY_MIN_KEYWORD_CHARS or abs(len(token) - len(keyword)) > 1:
        return False
    if token == keyword:
        return True
    if len(token) == len(keyword):
        diffs = [i for i in range(len(token)) if token[i] != keyword[i]]
        if len(diffs) == 1:
            return True
        if len(diffs) == 2:
            i, j = diffs
            return j == i + 1 and token[i] == keyword[j] and token[j] == keyword[i]
        return False
    # One insertion or deletion: align the shorter token against the longer one.
    short, long = (token, keyword) if len(token) < len(keyword) else (keyword, token)
    i = 0
    while i < len(short) and short[i] == long[i]:
        i += 1
    return short[i:] == long[i + 1 :]


def _token_matches(token: str, keyword: str) -> bool:
    """Exact token match, plural/stem variant, or a single typo."""
    if token == keyword:
        return True
    for suffix in ("ing", "es", "ed", "s"):
        if len(keyword) > len(suffix) + 3 and keyword.endswith(suffix):
            if token == keyword[: -len(suffix)]:
                return True
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            if token[: -len(suffix)] == keyword:
                return True
    return _within_one_typo(token, keyword)


def detect_scope(message: str) -> str | None:
    """Classify a prep-chat question into one of the three supported scopes.

    Returns ``"resume"``, ``"job_description"``, ``"interview_prep"``,
    or ``None`` when the question is outside all three scopes.
    Keyword-based and deterministic: no LLM call, cheap to test.
    """
    text = _normalize(message)
    if not text:
        return None
    tokens = _WORD_RE.findall(text)
    for scope, keywords in SCOPE_KEYWORDS.items():
        for keyword in keywords:
            if " " in keyword:
                if keyword in text:
                    return scope
            elif any(_token_matches(token, keyword) for token in tokens):
                return scope
    return None


def prep_coach_reply(
    message: str,
    context: str,
    history: list[dict] | None = None,
    *,
    llm=None,
) -> tuple[str, list[str]]:
    """Reply on the resume-improvement / preparation channel.

    The channel is scoped to three topics: the candidate's resume, the job
    description, and interview preparation. Out-of-scope questions get a
    deterministic redirect instead of an answer.

    Returns ``(reply, warnings)``. Never raises.
    """
    return _reply(
        message,
        context,
        history,
        persona=(
            "You are the CareerCrew preparation coach. You help with exactly three "
            "topics: (1) improving the candidate's resume, (2) clarifying the job "
            "description, and (3) preparing for the interview. If the candidate asks "
            "about anything else, politely redirect them to these three topics. "
            "Use only the context provided. Be specific and honest; "
            "never invent experience."
        ),
        scope_redirect=SCOPE_REDIRECT,
        llm=llm,
    )


def post_coach_reply(
    message: str,
    context: str,
    history: list[dict] | None = None,
    *,
    llm=None,
) -> tuple[str, list[str]]:
    """Reply on the post-interview performance channel (full context)."""
    return _reply(
        message,
        context,
        history,
        persona=(
            "You are the CareerCrew post-interview coach. You have the job "
            "description, the resume, the gap report, the prep plan, the full mock "
            "interview transcript, the per-question evaluations, and the overall "
            "score. Answer any follow-up question about performance and next steps, "
            "grounded only in that material."
        ),
        llm=llm,
    )


def _reply(
    message: str,
    context: str,
    history: list[dict] | None,
    *,
    persona: str,
    scope_redirect: str | None = None,
    llm=None,
) -> tuple[str, list[str]]:
    message = (message or "").strip()
    if not message:
        return "Ask a question and I'll help using your resume, the role, and your results.", []

    # Input guardrail: the message is untrusted; reject oversized or injected input.
    problems = guardrails.validate_interview_answer(message, max_chars=4000)
    if problems:
        return (
            "I can't act on that message. " + "; ".join(problems) + ". "
            "Ask a normal question about your resume, the role, or your results.",
            [],
        )

    # Scope guardrail (prep channel only): stay on the resume, the job
    # description, or interview preparation; redirect anything else.
    if scope_redirect is not None and detect_scope(message) is None:
        return scope_redirect, []

    answer = ""
    if llm is not None:
        try:
            prompt = (
                f"{persona}\n\n{context}\n\n"
                f"## Conversation so far\n{_history_text(history)}\n\n"
                f"## Candidate question\n{message}\n\nAnswer:"
            )
            answer = (llm(prompt) or "").strip()
        except Exception as exc:  # noqa: BLE001 - fall back, never crash
            logger.warning("coach LLM failed: %s", exc)
            answer = ""

    warnings: list[str] = []
    if not answer:
        answer = _fallback_reply(message, context)
        warnings.append("Coach used the offline fallback reply.")

    problems = guardrails.validate_coaching_reply(answer, context_text=context)
    if problems:
        warnings.extend(problems)
    return answer, warnings


def _fallback_reply(message: str, context: str) -> str:
    """A deterministic, honest reply when no LLM is available."""
    lower = message.lower()
    if any(word in lower for word in ("gap", "weak", "missing", "lack", "struggle")):
        return (
            "Use the gap report to separate what you genuinely cover from what you "
            "don't. For each uncovered requirement, prepare an honest answer: name a "
            "related skill you do have, then describe the concrete way you'd close "
            "the gap. Never claim experience your resume doesn't support. "
            "(Add an API key for a tailored answer using your own materials.)"
        )
    if any(word in lower for word in ("score", "performance", "how did i", "feedback", "review")):
        return (
            "Look at the per-question evaluations: they list what the interviewer was "
            "listening for and what to improve. Prioritize the lowest-scoring answers "
            "and rework them with the action-result structure (situation, your action, "
            "the measurable outcome). (Add an API key for a tailored review.)"
        )
    if any(word in lower for word in ("resume", "bullet", "rewrite", "improve")):
        return (
            "Rewrite each bullet as action + result, and only use facts already in your "
            "resume. Start with the bullets tied to the highest-priority gaps in your "
            "prep plan. (Add an API key for specific rewrites.)"
        )
    return (
        "Here's what I can say from your materials: focus your practice on the "
        "highest-priority gaps in your prep plan, keep every answer anchored to a real "
        "example from your resume, and end each answer with a measurable outcome. "
        "(Add an API key for a fully tailored answer.)"
    )
