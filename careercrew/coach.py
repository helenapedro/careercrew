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

    anchors = context_anchors(
        profile=profile,
        requirements=requirements,
        gaps=gaps,
        prep_plan=prep_plan,
    )
    if anchors:
        parts.append("## Topics in this analysis\n" + ", ".join(sorted(anchors)))

    if profile is not None:
        parts.append("## Candidate profile (from the resume)\n" + profile.model_dump_json())
    if requirements is not None:
        parts.append(
            "## Job requirements (from the job description)\n" + requirements.model_dump_json()
        )
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
        "resume",
        "cv",
        "bullet",
        "rewrite",
        "experience",
        "skill",
        "background",
        "job title",
        "employment",
        "internship",
        "career",
    ),
    "job_description": (
        "job description",
        "jd",
        "posting",
        "requirement",
        "role",
        "responsibilities",
        "qualification",
        "mean by",
        "company",
    ),
    "interview_prep": (
        "interview",
        "prep",
        "prepare",
        "preparation",
        "study",
        "readiness",
        "practice",
        "mock",
        "question",
        "nervous",
        "tips",
        "advice",
        "star",
        "behavioral",
        "tell me about",
        "walk through",
        "gap",
        "weakness",
        "strength",
        "technical",
        "coding",
        "whiteboard",
        "rehearse",
        "get ready",
        "brush up",
        "focus",
        "prioritize",
        "priority",
        "spend my time",
    ),
}

# Clearly unrelated domains. Only these are redirected outright. Unknown or
# ambiguous phrasing is allowed through to the persona, which is itself
# instructed to redirect off-topic questions. This is deliberately fail-open:
# bouncing a real preparation question costs the candidate far more than
# answering a stray one gracefully.
OFF_TOPIC_WORDS: tuple[str, ...] = (
    "weather",
    "joke",
    "poem",
    "recipe",
    "cook",
    "pasta",
    "restaurant",
    "movie",
    "film",
    "song",
    "lyrics",
    "football",
    "soccer",
    "basketball",
    "match",
    "game",
    "lottery",
    "stock",
    "crypto",
    "bitcoin",
    "flight",
    "hotel",
    "vacation",
    "weight",
    "diet",
    "workout",
    "doctor",
    "medical",
    "symptom",
    "diagnosis",
    "translate",
    "translation",
    "capital",
    "president",
    "election",
    "politics",
    "quantum",
    "planet",
    "universe",
    "cat",
    "dog",
    "gardening",
    "guitar",
    "piano",
    "chess",
    "pasta",
)

SCOPE_REDIRECT = (
    "I can help with three things: your resume, the job description, "
    "or interview preparation. Could you ask about one of those?"
)

# Generic "how do I learn this" phrasing. On its own it says nothing about the
# role, so it only counts when the question also names something from *this*
# analysis (a skill, technology, or requirement) or a prep topic.
GENERIC_PREP_WORDS: tuple[str, ...] = (
    "learn",
    "learning",
    "first step",
    "get started",
    "where do i start",
    "roadmap",
    "fundamentals",
    "basics",
    "course",
    "tutorial",
    "study",
    "guide",
    "resources",
)

# Structural / boilerplate words that appear in the assembled context but say
# nothing about the role. Excluded so they cannot act as relevance anchors.
_ANCHOR_STOPWORDS: frozenset[str] = frozenset(
    {
        "from",
        "that",
        "this",
        "with",
        "have",
        "your",
        "what",
        "when",
        "which",
        "will",
        "were",
        "been",
        "they",
        "them",
        "then",
        "than",
        "there",
        "their",
        "about",
        "into",
        "over",
        "under",
        "also",
        "more",
        "most",
        "some",
        "such",
        "only",
        "just",
        "like",
        "make",
        "made",
        "used",
        "use",
        "using",
        "each",
        "every",
        "other",
        "same",
        "does",
        "doing",
        "done",
        "would",
        "could",
        "should",
        "must",
        "may",
        "might",
        "can",
        "cannot",
        "and",
        "for",
        "the",
        "but",
        "not",
        "you",
        "are",
        "was",
        "has",
        "had",
        "its",
        "his",
        "her",
        "our",
        "out",
        "any",
        "all",
        "one",
        "two",
        "how",
        "why",
        "who",
        "where",
        "context",
        "candidate",
        "profile",
        "report",
        "plan",
        "requirements",
        "coaching",
        "guidelines",
        "json",
        "full_name",
        "skills",
        "required_skills",
        "seniority",
        "role",
        "title",
        "text",
        "name",
        "coverage_score",
        "verdicts",
        "verdict",
        "requirement",
        "evidence",
        "quote",
        "section",
        "prep",
        "interview",
        "resume",
        "job",
        "description",
        "gap",
        "gaps",
        "answer",
        "question",
        "questions",
    }
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


def context_anchors(*, profile=None, requirements=None, gaps=None, prep_plan=None) -> set[str]:
    """Terms that identify *this* analysis: skills, requirements, gaps, titles.

    Built from the structured models rather than the rendered prompt, so generic
    coaching prose ("give concrete examples", "take time") can never act as a
    relevance anchor.
    """

    def _collect(*values) -> set[str]:
        out: set[str] = set()
        for value in values:
            if not value:
                continue
            items = value if isinstance(value, (list, tuple, set)) else [value]
            for item in items:
                for token in _WORD_RE.findall(_normalize(str(item))):
                    if len(token) < 3 or token.isdigit() or token in _ANCHOR_STOPWORDS:
                        continue
                    out.add(token)
        return out

    anchors: set[str] = set()
    if profile is not None:
        anchors |= _collect(
            getattr(profile, "full_name", None),
            getattr(profile, "summary", None),
            getattr(profile, "skills", None),
            getattr(profile, "education", None),
            [f"{w.title} {w.company}" for w in getattr(profile, "experience", [])],
        )
    if requirements is not None:
        anchors |= _collect(
            getattr(requirements, "required_skills", None),
            getattr(requirements, "keywords", None),
            getattr(requirements, "nice_to_have", None),
            getattr(requirements, "seniority", None),
        )
    if gaps is not None:
        anchors |= _collect(
            [getattr(v, "requirement", None) for v in getattr(gaps, "verdicts", [])]
        )
    if prep_plan is not None:
        anchors |= _collect(
            [getattr(f, "area", None) for f in getattr(prep_plan, "focus_areas", [])],
            getattr(prep_plan, "question_themes", None),
            getattr(prep_plan, "risk_areas", None),
            getattr(prep_plan, "strengths", None),
        )
    return anchors


def _context_anchors(context: str) -> set[str]:
    """Anchors embedded in an already-built context (the "Topics" section).

    Falls back to scanning the analysis sections (not the coaching guidelines)
    so a context assembled elsewhere still works.
    """
    body = (context or "").split("## Coaching guidelines")[0]
    marker = "## Topics in this analysis\n"
    if marker in body:
        body = body.split(marker, 1)[1].split("\n##", 1)[0]
    anchors: set[str] = set()
    for token in _WORD_RE.findall(_normalize(body)):
        if len(token) < 3 or token in _ANCHOR_STOPWORDS or token.isdigit():
            continue
        anchors.add(token)
    return anchors


def _anchored_to_context(message: str, anchors: set[str]) -> bool:
    """True when the question actually refers to something from this analysis."""
    tokens = _WORD_RE.findall(_normalize(message))
    for token in tokens:
        if len(token) < 3 or token in _ANCHOR_STOPWORDS:
            continue
        if any(_token_matches(token, anchor) for anchor in anchors):
            return True
    return False


def _is_off_topic(tokens: list[str]) -> bool:
    """True only for a recognized off-topic domain (weather, recipes, ...)."""
    for word in OFF_TOPIC_WORDS:
        if any(_token_matches(token, word) for token in tokens):
            return True
    return False


def detect_scope(message: str, context: str | None = None) -> str | None:
    """Classify a prep-chat question into one of the three supported scopes.

    Returns ``"resume"``, ``"job_description"``, ``"interview_prep"``, or
    ``None`` when the question is not about this analysis.

    Relevance is anchored to **the analysis on screen**: when ``context`` is
    given, a question must reference something from it (a required skill, a
    technology, a role title, or a gap) to be in scope. This keeps the coach on
    the candidate's resume, this job description, and preparation for this role,
    while still answering phrasing that uses no preparation keyword such as
    "what I have to do in the first step for learn Kubernetes?" — because
    Kubernetes is named in this analysis.

    A recognized off-topic topic is always rejected, and so is a question that
    shares nothing with this analysis. Deterministic: no LLM call.
    """
    text = _normalize(message)
    if not text:
        return None
    tokens = _WORD_RE.findall(text)
    if _is_off_topic(tokens):
        return None

    for scope, keywords in SCOPE_KEYWORDS.items():
        for keyword in keywords:
            if " " in keyword:
                if keyword in text:
                    return scope
            elif any(_token_matches(token, keyword) for token in tokens):
                return scope

    # No explicit prep keyword. Accept generic "how do I learn X" phrasing only
    # when X is something this analysis actually talks about.
    anchors = _context_anchors(context) if context else set()
    mentions_generic = any(
        (keyword in text) if " " in keyword else any(_token_matches(t, keyword) for t in tokens)
        for keyword in GENERIC_PREP_WORDS
    )
    if mentions_generic:
        if not anchors or _anchored_to_context(message, anchors):
            return "interview_prep"
        return None

    # A question that names this role's skills/technologies is about preparation
    # for it, even when worded without any prep keyword.
    if anchors and _anchored_to_context(message, anchors):
        return "interview_prep"

    # Otherwise the question shares nothing with this analysis: redirect it.
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
            "topics: (1) improving the candidate's resume, (2) clarifying this job "
            "description, and (3) preparing for this interview — including learning "
            "the technologies and skills this role requires. Stay on this analysis: "
            "the candidate's resume, this job description, and preparation for this "
            "role. If a question has nothing to do with them (weather, recipes, sport, "
            "shopping, general trivia), politely redirect to those three topics in one "
            "short sentence. When a request plausibly relates to preparing for this "
            "role, answer it helpfully instead of asking them to rephrase. "
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
    # description, or interview preparation for this role; redirect anything else.
    if scope_redirect is not None and detect_scope(message, context) is None:
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
