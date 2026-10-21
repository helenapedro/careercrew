"""Mock interview and coaching-chat callbacks.

What it does: starts a practice interview, scores each answer, and replies in the coach chats.
Who calls it: the Mock interview and coach buttons wired in app.py.
What it returns: Gradio updates for the question, transcript, scores, and chat history.
"""

from __future__ import annotations

from careercrew import audio, coach, guardrails, interview, llm
from careercrew.callbacks_analyze import _context_models, _load_context
from careercrew.models import (
    AnswerEvaluation,
    InterviewQuestion,
    InterviewTurnRole,
    MockInterviewSession,
)
from careercrew.services import STORE as _STORE
from careercrew.ui_html import _alert_html, _esc

def _turns_to_messages(session: MockInterviewSession) -> list[dict]:
    """Convert the transcript to Gradio chatbot messages (interviewer = assistant)."""
    messages: list[dict] = []
    for turn in session.turns:
        role = "assistant" if turn.role is InterviewTurnRole.INTERVIEWER else "user"
        messages.append({"role": role, "content": turn.text})
    return messages


def _question_html(question: InterviewQuestion | None, *, done: bool = False) -> str:
    if done or question is None:
        return (
            "<div class='cc-card'><h3>Interview complete</h3>"
            "<div class='cc-empty'><strong>You finished the mock interview</strong>"
            "Review your score and the per-question feedback below, then ask the "
            "post-interview coach anything you like.</div></div>"
        )
    return (
        "<div class='cc-card'><h3>Interviewer</h3>"
        "<p class='cc-hint'>Question "
        f"{question.index + 1} of the mock interview</p>"
        f"<p style='font-size:16px;line-height:1.55;color:var(--cc-ink);margin:6px 0'>{_esc(question.text)}</p>"
        "<div class='cc-cite'>"
        "<span class='cc-cite-label'>Looking for</span>"
        "<span class='cc-cite-fact'>"
        f"{_esc(question.intent or question.target_competency or 'a grounded, specific answer')}"
        "</span></div>"
        "</div>"
    )


def _evaluation_html(evaluation: AnswerEvaluation | None) -> str:
    if evaluation is None:
        return ""
    strengths = "".join(f"<li>{_esc(s)}</li>" for s in evaluation.strengths)
    improvements = "".join(f"<li>{_esc(i)}</li>" for i in evaluation.improvements)
    outline = "".join(f"<li>{_esc(o)}</li>" for o in evaluation.model_answer_outline)
    return (
        "<div class='cc-card'><h3>Feedback on your answer</h3>"
        "<div class='cc-stats'>"
        f"<span class='cc-chip'>score · {int(evaluation.score)}/100</span>"
        "</div>"
        "<div class='cc-section-title'>What the interviewer was looking for</div>"
        f"<p style='color:var(--cc-ink-2);font-size:13.5px;line-height:1.55'>{_esc(evaluation.what_interviewer_wanted)}</p>"
        + (f"<div class='cc-section-title'>What worked</div><ul class='cc-list'>{strengths}</ul>" if strengths else "")
        + (f"<div class='cc-section-title'>What to improve</div><div class='cc-note'><ul class='cc-list'>{improvements}</ul></div>" if improvements else "")
        + (f"<div class='cc-section-title'>A stronger answer would</div><ul class='cc-list'>{outline}</ul>" if outline else "")
        + "</div>"
    )


def _overall_html(session: MockInterviewSession) -> str:
    if not session.completed:
        return ""
    return (
        "<div class='cc-card'><h3>Overall performance</h3>"
        "<div class='cc-meter'><div class='cc-meter-top'>"
        f"<div class='cc-score'>{int(session.overall_score)}<small>/100</small></div>"
        "<div class='cc-meter-label'>Average across your answers</div></div>"
        f"<div class='cc-bar'><span style='width:{int(session.overall_score)}%'></span></div></div>"
        f"<p style='color:var(--cc-ink-2);font-size:14px;line-height:1.6'>{_esc(session.overall_summary)}</p>"
        "</div>"
    )


def _audio_status() -> str:
    if audio.audio_available():
        return ""
    return (
        "<div class='cc-alert info'><strong>Text-only practice mode</strong>"
        "Voice is unavailable (no audio-capable API key), so questions are shown as "
        "text and you can type your answers. Add an OpenAI key to enable the voice "
        "interviewer.</div>"
    )


def interview_start(ctx_state, count: int) -> tuple:
    """Begin a mock interview: generate questions and ask the first one."""
    context = _load_context(ctx_state)
    if not context:
        return (
            _alert_html("Analyze a match first — the interview uses your resume and the role."),
            _question_html(None, done=True),
            None,
            [],
            "",
            "",
            None,
        )
    models = _context_models(context)
    questions = interview.generate_questions(
        models["profile"],
        models["requirements"],
        models["gaps"],
        models["prep_plan"],
        int(count or _SETTINGS.interview_question_count),
        llm=llm.callable_or_none(),
    )
    if not questions:
        return (
            _alert_html("No interview questions could be generated. Try analyzing again."),
            _question_html(None, done=True),
            None,
            [],
            "",
            "",
            None,
        )

    session = MockInterviewSession(
        session_id=interview.make_session_id(),
        role_title=(models["requirements"].seniority or "the role"),
        questions=questions,
    )
    return _ask_question(session, 0)


def _ask_question(session: MockInterviewSession, index: int, *, error: str = "") -> tuple:
    """Append the interviewer's question turn, synthesize audio, and render."""
    question = session.questions[index]
    audio_path = audio.speak(question.text) or ""
    question.audio_ref = audio_path
    interview.append_turn(
        session, InterviewTurnRole.INTERVIEWER, question.text, question_index=index
    )
    _STORE.save_interview(session)
    return (
        _alert_html(error) if error else _audio_status(),
        _question_html(question),
        audio_path or None,
        _turns_to_messages(session),
        "",
        "",
        session.model_dump_json(),
    )


def interview_submit(ctx_state, iv_state, answer_text, answer_audio) -> tuple:
    """Evaluate the candidate's answer, then move to the next question."""
    context = _load_context(ctx_state)
    session = _load_interview(iv_state)
    if context is None or session is None:
        return (
            _alert_html("Start the interview first."),
            _question_html(None, done=True),
            None,
            [],
            "",
            "",
            iv_state,
        )

    index = sum(1 for e in session.evaluations)
    if index >= len(session.questions):
        return (
            "",
            _question_html(None, done=True),
            None,
            _turns_to_messages(session),
            "",
            _overall_html(session),
            session.model_dump_json(),
        )

    question = session.questions[index]

    # Prefer the transcript of the recorded audio; fall back to typed text.
    transcript = audio.transcribe(answer_audio) if answer_audio else ""
    answer = transcript.strip() or (answer_text or "").strip()

    problems = guardrails.validate_interview_answer(answer)
    if problems:
        return (
            _alert_html("Please answer the question: " + "; ".join(problems)),
            _question_html(question),
            None,
            _turns_to_messages(session),
            _evaluation_html(session.evaluations[-1] if session.evaluations else None),
            "",
            session.model_dump_json(),
        )

    models = _context_models(context)
    context_bundle = {
        "role": models["requirements"].model_dump(),
        "gaps": models["gaps"].model_dump(),
        "prep_plan": models["prep_plan"].model_dump(),
    }
    evaluation = interview.evaluate_answer(
        question, answer, context_bundle, llm=llm.callable_or_none()
    )
    eval_problems = guardrails.validate_evaluation(evaluation)
    session.evaluations.append(evaluation)
    interview.append_turn(
        session,
        InterviewTurnRole.CANDIDATE,
        answer,
        question_index=index,
        audio_ref=str(answer_audio or ""),
    )

    next_index = index + 1
    if next_index < len(session.questions):
        session.overall_score = round(
            sum(e.score for e in session.evaluations) / len(session.evaluations)
        )
        _STORE.save_interview(session)
        question_out = _ask_question(session, next_index)
        # Splice the evaluation feedback into the returned tuple.
        return (
            question_out[0],
            question_out[1],
            question_out[2],
            question_out[3],
            _evaluation_html(evaluation),
            "",
            question_out[6],
        )

    # Final answer: finish the session and score it.
    score, summary = interview.overall_evaluation(session, llm=llm.callable_or_none())
    session.overall_score = score
    session.overall_summary = summary
    session.completed = True
    _STORE.save_interview(session)
    return (
        _alert_html("; ".join(eval_problems)) if eval_problems else _audio_status(),
        _question_html(None, done=True),
        None,
        _turns_to_messages(session),
        _evaluation_html(evaluation),
        _overall_html(session),
        session.model_dump_json(),
    )


def _load_interview(iv_state) -> MockInterviewSession | None:
    if not iv_state:
        return None
    try:
        return MockInterviewSession.model_validate_json(iv_state)
    except Exception:  # noqa: BLE001
        return None


def _render_prep_chat(history, message: str, ctx_state):
    """Prep coach: resume improvement + preparation chat."""
    history = history or []
    context = _load_context(ctx_state)
    context_text = coach.build_context() if context else "No analysis yet."
    if context:
        models = _context_models(context)
        context_text = coach.build_context(
            profile=models["profile"],
            requirements=models["requirements"],
            gaps=models["gaps"],
            prep_plan=models["prep_plan"],
        )
    prompt = message.get("text", "") if isinstance(message, dict) else str(message)
    reply, warnings = coach.prep_coach_reply(
        prompt, context_text, history, llm=llm.callable_or_none()
    )
    if warnings:
        reply += "\n\n_" + " ".join(warnings) + "_"
    history = history + [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": reply},
    ]
    session_id = _context_models(context)["package_id"] if context else "session"
    _STORE.add_chat_message(session_id, "prep", "user", prompt)
    _STORE.add_chat_message(session_id, "prep", "assistant", reply)
    return history, ""


def _render_post_chat(history, message: str, ctx_state, iv_state):
    """Post-interview coach: everything about JD, resume, and interview results."""
    history = history or []
    context = _load_context(ctx_state)
    session = _load_interview(iv_state) or _STORE.latest_interview()
    if context:
        models = _context_models(context)
        context_text = coach.build_context(
            profile=models["profile"],
            requirements=models["requirements"],
            gaps=models["gaps"],
            prep_plan=models["prep_plan"],
            interview=session,
            include_interview=session is not None,
        )
    else:
        context_text = coach.build_context(interview=session, include_interview=session is not None)
    prompt = message.get("text", "") if isinstance(message, dict) else str(message)
    reply, warnings = coach.post_coach_reply(
        prompt, context_text, history, llm=llm.callable_or_none()
    )
    if warnings:
        reply += "\n\n_" + " ".join(warnings) + "_"
    history = history + [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": reply},
    ]
    session_id = (session.session_id if session else None) or (
        _context_models(context)["package_id"] if context else "session"
    )
    _STORE.add_chat_message(session_id, "post", "user", prompt)
    _STORE.add_chat_message(session_id, "post", "assistant", reply)
    return history, ""

