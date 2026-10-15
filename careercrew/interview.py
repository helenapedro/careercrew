"""CareerCrew - Virtual Mock Interviewer.

Pure logic for the mock interview (the Gradio wiring lives in ``app.py``):

* ``generate_questions`` - interviewer questions grounded in the JD, resume,
  gaps, and prep plan.
* ``evaluate_answer``    - real-time per-answer critique: what the interviewer
  wanted, what worked, what to improve, and a model answer outline.
* ``overall_evaluation`` - a session summary and overall score.

Every function has a deterministic fallback so a session still works without an
LLM key, and every output is validated by ``careercrew.guardrails`` before it is
shown. Nothing here submits anything; it is practice only.
"""

from __future__ import annotations

import logging
import re
import uuid

from careercrew import guardrails
from careercrew.models import (
    AnswerEvaluation,
    InterviewPrepPlan,
    InterviewQuestion,
    InterviewTurnRole,
    MockInterviewSession,
    TranscriptTurn,
)

logger = logging.getLogger("careercrew.interview")


def make_session_id() -> str:
    return f"int-{uuid.uuid4().hex[:8]}"


def _keywords(*texts: str, limit: int = 40) -> list[str]:
    stop = {
        "with", "that", "this", "from", "have", "your", "will", "would", "about",
        "their", "them", "they", "into", "over", "under", "role", "work", "team",
        "years", "year", "experience", "using", "need", "must", "plus", "nice",
    }
    seen: list[str] = []
    for text in texts:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{2,}", text or ""):
            key = token.strip(".,;:")
            low = key.lower()
            if low and low not in stop and low not in [s.lower() for s in seen]:
                seen.append(key)
            if len(seen) >= limit:
                return seen
    return seen


def generate_questions(
    profile,
    requirements,
    gaps,
    plan: InterviewPrepPlan | None = None,
    count: int = 5,
    *,
    llm=None,
) -> list[InterviewQuestion]:
    """Produce interviewer questions.

    Uses the LLM when available, otherwise derives questions deterministically
    from the highest-priority gaps, the requirements, and the prep-plan themes.
    Questions never assert facts absent from the provided context.
    """
    questions: list[InterviewQuestion] = []
    if llm is not None:
        try:
            raw = llm(_build_question_prompt(profile, requirements, gaps, plan, count))
            questions = _parse_questions(raw, count)
        except Exception as exc:  # noqa: BLE001 - fall back, never crash
            logger.warning("question generation failed: %s", exc)
    if not questions:
        questions = _fallback_questions(profile, requirements, gaps, plan, count)
    return questions


def _build_question_prompt(profile, requirements, gaps, plan, count: int) -> str:
    themes = ", ".join((plan.question_themes if plan else [])[:8])
    return (
        f"Act as a hiring interviewer. Write {count} interview questions for this "
        "role. Ground every question in the job requirements and the candidate's "
        "resume facts below; never assert facts about the candidate that are not "
        "present. Target the biggest gaps. Return ONLY JSON:\n"
        '{"questions": [{"text": str, "intent": str, "target_competency": str, '
        '"source": str}]}\n\n'
        f"Themes to consider: {themes}\n\n"
        f"PROFILE:\n{profile.model_dump_json()}\n\n"
        f"REQUIREMENTS:\n{requirements.model_dump_json()}\n\n"
        f"GAPS:\n{gaps.model_dump_json()}\n"
    )


def _parse_questions(raw: str, count: int) -> list[InterviewQuestion]:
    from careercrew.pipeline import extract_json

    data = extract_json(raw)
    if not isinstance(data, dict):
        return []
    out: list[InterviewQuestion] = []
    for index, item in enumerate(data.get("questions") or []):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        out.append(
            InterviewQuestion(
                index=index,
                text=text,
                intent=str(item.get("intent") or "").strip(),
                target_competency=str(item.get("target_competency") or "").strip(),
                source=str(item.get("source") or "").strip(),
            )
        )
        if len(out) >= count:
            break
    return out


def _fallback_questions(profile, requirements, gaps, plan, count: int) -> list[InterviewQuestion]:
    out: list[InterviewQuestion] = []

    def add(text: str, intent: str, competency: str, source: str) -> None:
        if len(out) < count:
            out.append(
                InterviewQuestion(
                    index=len(out),
                    text=text,
                    intent=intent,
                    target_competency=competency,
                    source=source,
                )
            )

    for verdict in gaps.verdicts:
        if (verdict.verdict or "").lower().startswith("out"):
            add(
                f"The role asks for {verdict.requirement}, which isn't on your resume yet. "
                f"How would you get up to speed, and what related experience can you draw on?",
                "How you handle a genuine gap honestly and how you learn.",
                verdict.requirement,
                verdict.requirement,
            )
    for verdict in gaps.verdicts:
        if (verdict.verdict or "").lower().startswith("reframe"):
            add(
                f"Tell me about a time your work touched on {verdict.requirement}. "
                "What did you do and what was the result?",
                "Whether related experience transfers clearly to the requirement.",
                verdict.requirement,
                verdict.requirement,
            )
    for skill in list(requirements.required_skills)[:4]:
        add(
            f"Walk me through a project where you used {skill}. What was your specific "
            "contribution and the measurable outcome?",
            "Depth and ownership in a core required skill.",
            skill,
            skill,
        )
    for skill in list(profile.skills)[:3]:
        add(
            f"You list {skill} on your resume — describe the most complex problem you "
            "solved with it and the trade-offs you weighed.",
            "Evidence depth behind a claimed skill.",
            skill,
            skill,
        )
    add(
        "Tell me about a time you disagreed with a teammate or stakeholder. How did you "
        "resolve it, and what was the outcome?",
        "Collaboration and conflict handling.",
        "collaboration",
        "general",
    )
    add(
        "Describe a project that failed or missed its goal. What did you learn, and what "
        "would you do differently?",
        "Self-awareness and learning from failure.",
        "reflection",
        "general",
    )
    return out[:count]


def evaluate_answer(
    question: InterviewQuestion,
    answer: str,
    context: dict | None = None,
    *,
    llm=None,
) -> AnswerEvaluation:
    """Critique one answer: what the interviewer wanted, plus what to improve."""
    context = context or {}
    if llm is not None:
        try:
            raw = llm(_build_eval_prompt(question, answer, context))
            parsed = _parse_evaluation(raw, question, answer)
            if parsed is not None:
                return parsed
        except Exception as exc:  # noqa: BLE001 - fall back, never crash
            logger.warning("answer evaluation failed: %s", exc)
    return _fallback_evaluation(question, answer, context)


def _build_eval_prompt(question: InterviewQuestion, answer: str, context: dict) -> str:
    return (
        "You are a supportive but honest interview coach. Evaluate the candidate's "
        "answer to the interview question. Base every point on the question, the "
        "answer, and the role context provided. Do not invent experience for the "
        "candidate. Return ONLY JSON:\n"
        '{"score": int (0-100), "what_interviewer_wanted": str, "strengths": [str], '
        '"improvements": [str], "model_answer_outline": [str]}\n\n'
        f"QUESTION: {question.text}\n"
        f"INTERVIEWER INTENT: {question.intent}\n"
        f"CANDIDATE ANSWER: {answer}\n\n"
        f"ROLE CONTEXT:\n{context}\n"
    )


def _parse_evaluation(raw: str, question: InterviewQuestion, answer: str):
    from careercrew.pipeline import extract_json

    data = extract_json(raw)
    if not isinstance(data, dict):
        return None
    try:
        return AnswerEvaluation(
            question_index=question.index,
            question=question.text,
            answer=answer,
            score=int(data.get("score", 0)),
            what_interviewer_wanted=str(data.get("what_interviewer_wanted") or ""),
            strengths=[str(s) for s in (data.get("strengths") or []) if str(s).strip()],
            improvements=[str(s) for s in (data.get("improvements") or []) if str(s).strip()],
            model_answer_outline=[
                str(s) for s in (data.get("model_answer_outline") or []) if str(s).strip()
            ],
        )
    except Exception:  # noqa: BLE001 - bounded repair
        return None


def _fallback_evaluation(
    question: InterviewQuestion, answer: str, context: dict
) -> AnswerEvaluation:
    """Heuristic, deterministic evaluation used without an LLM key.

    It rewards concrete structure and specifics (numbers, "I" ownership, outcome
    words) and always returns at least one improvement, so the feedback stays
    actionable.
    """
    text = (answer or "").strip()
    words = text.split()
    length = len(words)
    lower = text.lower()

    score = 55
    strengths: list[str] = []
    improvements: list[str] = []

    if length >= 60:
        score += 12
        strengths.append("Gave a developed answer with enough detail to follow.")
    elif length >= 25:
        score += 5
        strengths.append("Covered the question at a high level.")
    else:
        improvements.append("Expand the answer with a concrete example and a clear outcome.")

    if re.search(r"\d", text):
        score += 10
        strengths.append("Included specifics or metrics, which makes the answer credible.")
    else:
        improvements.append("Add a number or measurable result to make the impact concrete.")

    if re.search(r"\b(i|my|we)\b", lower) and re.search(r"\b(result|impact|led|built|shipped|improved|reduced|increased)\b", lower):
        score += 12
        strengths.append("Used action-and-result framing rather than just describing duties.")
    else:
        improvements.append(
            "Use an action-result structure (situation, what YOU did, the outcome)."
        )

    if question.target_competency and question.target_competency.lower() not in lower:
        improvements.append(
            f"Connect the answer explicitly to {question.target_competency}."
        )

    if not strengths:
        strengths.append("Engaged with the question directly.")
    if not improvements:
        improvements.append("Tighten the ending with a one-sentence takeaway.")

    score = max(0, min(100, score))
    outline = [
        "Open with a one-line summary of the situation.",
        "Explain your specific role and the actions you took.",
        "Quantify the result and name what you learned.",
    ]
    return AnswerEvaluation(
        question_index=question.index,
        question=question.text,
        answer=text,
        score=score,
        what_interviewer_wanted=(
            question.intent
            or f"Evidence of real experience with {question.target_competency or 'the requirement'}."
        ),
        strengths=strengths,
        improvements=improvements,
        model_answer_outline=outline,
    )


def append_turn(
    session: MockInterviewSession,
    role: InterviewTurnRole,
    text: str,
    *,
    question_index: int = 0,
    audio_ref: str = "",
) -> TranscriptTurn:
    """Append a validated turn to the session transcript and return it."""
    turn = TranscriptTurn(
        role=role,
        text=(text or "").strip(),
        question_index=question_index,
        audio_ref=audio_ref,
    )
    problems = guardrails.validate_transcript_turn(turn)
    if problems:
        logger.warning("invalid transcript turn: %s", problems)
    session.turns.append(turn)
    return turn


def overall_evaluation(session: MockInterviewSession, *, llm=None) -> tuple[int, str]:
    """Return (overall_score, summary) for a finished session."""
    scores = [e.score for e in session.evaluations]
    base = round(sum(scores) / len(scores)) if scores else 0
    all_improvements: list[str] = []
    for evaluation in session.evaluations:
        all_improvements.extend(evaluation.improvements)

    if llm is not None:
        try:
            raw = llm(_build_overall_prompt(session, base))
            summary = _parse_overall(raw) or _fallback_summary(session, base)
            return base, summary
        except Exception:  # noqa: BLE001
            pass
    return base, _fallback_summary(session, base)


def _build_overall_prompt(session: MockInterviewSession, base: int) -> str:
    transcript = "\n".join(
        f"{turn.role.value.upper()}: {turn.text}" for turn in session.turns
    )
    return (
        "You are an interview coach. Summarize this mock interview in 3-5 sentences: "
        "overall performance, the strongest signals, and the top 2 priorities to "
        "improve. Return plain text only. Do not invent experience.\n\n"
        f"ROUGHLY AVERAGED SCORE: {base}\n\nTRANSCRIPT:\n{transcript}\n"
    )


def _parse_overall(raw: str) -> str:
    if not raw:
        return ""
    return raw.strip().strip("`").strip()


def _fallback_summary(session: MockInterviewSession, base: int) -> str:
    strength = ""
    weak = ""
    for evaluation in session.evaluations:
        if evaluation.strengths and not strength:
            strength = evaluation.strengths[0]
        if evaluation.improvements and not weak:
            weak = evaluation.improvements[0]
    parts = [f"You scored an average of {base}/100 across {len(session.evaluations)} answer(s)."]
    if strength:
        parts.append(f"Strongest signal: {strength}")
    if weak:
        parts.append(f"Top priority to improve: {weak}")
    return " ".join(parts)
