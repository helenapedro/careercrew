"""CareerCrew - full-memory coaching chats.

Two candidate-facing chat channels, both grounded in everything the pipeline
already produced:

* **prep_coach_reply** - resume improvement and interview preparation.
* **post_coach_reply** - post-interview performance and follow-up, with the
  mock interview transcript, per-question evaluations, and overall score in
  context.

The context builder is bounded (character-capped) so prompts stay a reasonable
size, and every reply is checked by ``careercrew.guardrails.validate_coaching_reply``.
Both channels degrade to a deterministic, still-useful reply without an LLM key.
"""

from __future__ import annotations

import logging

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


def prep_coach_reply(
    message: str,
    context: str,
    history: list[dict] | None = None,
    *,
    llm=None,
) -> tuple[str, list[str]]:
    """Reply on the resume-improvement / preparation channel.

    Returns ``(reply, warnings)``. Never raises.
    """
    return _reply(
        message,
        context,
        history,
        persona=(
            "You are the CareerCrew preparation coach. Help the candidate improve "
            "their resume and prepare for the interview, using only the context "
            "provided. Be specific and honest; never invent experience."
        ),
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
