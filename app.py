"""CareerCrew - candidate-facing Gradio product UI.

What it does: builds the page and wires buttons to the callbacks.
Who calls it: `python app.py`, and the smoke tests.
What it returns: a running Gradio app (see main).
"""

from __future__ import annotations

import logging
import os

import gradio as gr

from careercrew import callbacks_analyze, callbacks_interview, services
from careercrew.callbacks_analyze import (
    _IDLE_STATUS,
    _empty_outputs,
    analyze,
    approve,
    reject,
    request_revision,
)
from careercrew.callbacks_interview import (
    _question_html,
    _render_post_chat,
    _render_prep_chat,
    interview_start,
    interview_submit,
)
from careercrew.config import get_settings
from careercrew.review import PackageReviewService
from careercrew.session_store import SessionStore
from careercrew.ui_css import CUSTOM_CSS, LIGHT_MODE_JS
from careercrew.ui_html import (
    _hero,
    _insight_html,
    _prep_html,
    _review_guide_html,
    _stages_html,
    _topbar,
)
from careercrew.ui_state import OUTPUT_ORDER

logging.basicConfig(level=get_settings().log_level)


def _bind_runtime() -> None:
    """Point every callback at the current settings.

    Importing app (or reloading it in tests) rebuilds the store so a test can
    point CAREERCREW_UPLOAD_DIR and CAREERCREW_DB_PATH at a temp folder first.
    """
    settings = get_settings()
    store = SessionStore(settings.db_path)
    review = PackageReviewService(store)
    services.SETTINGS = settings
    services.STORE = store
    services.REVIEW = review
    callbacks_analyze._SETTINGS = settings
    callbacks_analyze._STORE = store
    callbacks_analyze._REVIEW = review
    callbacks_interview._STORE = store
    global _SETTINGS, _STORE, _REVIEW
    _SETTINGS = settings
    _STORE = store
    _REVIEW = review


_bind_runtime()

_SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")

def _read_sample(name: str) -> str:
    try:
        with open(os.path.join(_SAMPLES_DIR, name), encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #
def build_app() -> gr.Blocks:
    """Build the Gradio page and wire every button to its callback."""
    with gr.Blocks(title="CareerCrew — Match your resume to the role") as demo:
        state = gr.State(None)
        ctx_state = gr.State(None)
        iv_state = gr.State(None)

        gr.HTML(_topbar())
        gr.HTML(_hero())

        with gr.Tabs(elem_classes=["cc-main-tabs"]):
            # ------------------------------------------------------------------ #
            # Tab 1 — Analyze (inputs, progress, results, HITL decision)
            # ------------------------------------------------------------------ #
            with gr.Tab("1 · Analyze match"):
                gr.HTML(
                    "<div class='cc-panel-head' style='margin-bottom:10px'>"
                    "<h3>Analyze match</h3>"
                    "<p class='cc-hint'>Add your resume and the job posting, run Analyze, "
                    "watch progress here, review the result sub-tabs, then approve or "
                    "add missing experience. Progress and decisions live only in this tab.</p></div>"
                )

                with gr.Row(equal_height=True):
                    with gr.Column(scale=1):
                        with gr.Group(elem_classes=["cc-panel"]):
                            gr.HTML(
                                "<div class='cc-panel-head'><h3>Your resume</h3>"
                                "<p class='cc-hint'>Upload a file or paste the text.</p></div>"
                            )
                            sample_resume_btn = gr.Button("Try a sample resume", size="sm")
                            with gr.Tabs():
                                with gr.Tab("Upload file"):
                                    resume_file = gr.File(
                                        label="PDF, DOCX, or TXT",
                                        file_types=[".pdf", ".docx", ".txt"],
                                        elem_classes=["cc-field"],
                                    )
                                with gr.Tab("Paste text"):
                                    resume_text = gr.Textbox(
                                        label="Resume text",
                                        placeholder="Paste your resume here…",
                                        lines=12,
                                        elem_classes=["cc-field"],
                                        show_label=False,
                                    )

                    with gr.Column(scale=1):
                        with gr.Group(elem_classes=["cc-panel"]):
                            gr.HTML(
                                "<div class='cc-panel-head'><h3>The job</h3>"
                                "<p class='cc-hint'>Upload the posting or paste the text. "
                                "URLs are not read directly.</p></div>"
                            )
                            sample_jd_btn = gr.Button("Try a sample job", size="sm")
                            with gr.Tabs():
                                with gr.Tab("Upload file"):
                                    jd_file = gr.File(
                                        label="PDF, DOCX, or TXT",
                                        file_types=[".pdf", ".docx", ".txt"],
                                        elem_classes=["cc-field"],
                                    )
                                with gr.Tab("Paste posting"):
                                    jd_text = gr.Textbox(
                                        label="Job description",
                                        placeholder="Paste the job description here…",
                                        lines=10,
                                        elem_classes=["cc-field"],
                                        show_label=False,
                                    )

                with gr.Row(elem_classes=["cc-cta"], equal_height=True):
                    gr.HTML(
                        "<div class='cc-cta-copy'><h3>Ready when you are</h3>"
                        "<p>We’ll score the match, plan interview prep, and suggest "
                        "stronger, evidence-backed bullets.</p></div>",
                        elem_classes=["cc-cta-copy-wrap"],
                    )
                    with gr.Row(elem_classes=["cc-cta-actions"]):
                        run_btn = gr.Button(
                            "Analyze match",
                            variant="primary",
                            elem_classes=["cc-run"],
                            scale=0,
                            min_width=168,
                        )
                        clear_btn = gr.Button(
                            "Clear", elem_classes=["cc-clear"], scale=0, min_width=88
                        )

                error_box = gr.HTML("", elem_classes=["cc-alert-slot"])
                status = gr.Markdown(_IDLE_STATUS, elem_classes=["cc-status-line"])
                stages_html = gr.HTML(_stages_html(-1))

                with gr.Tabs(elem_classes=["cc-result-tabs"]):
                    with gr.Tab("Match report"):
                        insight_html = gr.HTML(_insight_html(None))
                    with gr.Tab("Interview prep plan"):
                        prep_html = gr.HTML(_prep_html(None))

                with gr.Group(elem_classes=["cc-review"]):
                    review_guide_html = gr.HTML(_review_guide_html("idle"))

                    with gr.Group(elem_classes=["cc-review-choice", "cc-review-choice-a"]):
                        gr.HTML(
                            "<div class='cc-choice-label'>"
                            "<span class='cc-choice-n'>A</span>"
                            "<div><strong>Approve</strong> — the prep bundle looks right. "
                            "Nothing is sent to an employer; this only finalizes it here.</div></div>"
                        )
                        approve_btn = gr.Button(
                            "Approve prep bundle",
                            variant="primary",
                            interactive=False,
                            elem_classes=["cc-approve"],
                        )

                    with gr.Group(elem_classes=["cc-review-choice", "cc-review-choice-b"]):
                        gr.HTML(
                            "<div class='cc-choice-label'>"
                            "<span class='cc-choice-n'>B</span>"
                            "<div><strong>Add missing experience</strong> — e.g. the JD wants "
                            "React but your resume doesn’t list it. Type the update, then press "
                            "the button. <em>Analyze runs again automatically</em> and refreshes "
                            "Match and Prep.</div></div>"
                        )
                        feedback = gr.Textbox(
                            label="Your experience update",
                            placeholder=(
                                "e.g. I have 5+ years of React experience building production SPAs."
                            ),
                            lines=3,
                            interactive=False,
                            elem_classes=["cc-field"],
                        )
                        revise_btn = gr.Button(
                            "Apply updates & re-analyze",
                            interactive=False,
                            elem_classes=["cc-revise"],
                        )

                    with gr.Group(elem_classes=["cc-review-choice", "cc-review-choice-c"]):
                        gr.HTML(
                            "<div class='cc-choice-label'>"
                            "<span class='cc-choice-n'>C</span>"
                            "<div><strong>Reject</strong> — discard this prep bundle.</div></div>"
                        )
                        reject_btn = gr.Button(
                            "Reject prep bundle",
                            interactive=False,
                            elem_classes=["cc-reject"],
                        )

                    review_status = gr.Markdown("", elem_classes=["cc-review-status"])

            # ------------------------------------------------------------------ #
            # Tab 2 — Prep coach
            # ------------------------------------------------------------------ #
            with gr.Tab("2 · Prep coach"):
                gr.HTML(
                    "<div class='cc-panel-head'><h3>Resume &amp; preparation coach</h3>"
                    "<p class='cc-hint'>Ask anything about improving your resume or preparing "
                    "for this role. Uses your Analyze context when available.</p></div>"
                )
                prep_chat = gr.Chatbot(label="Chat", height=380, show_label=False)
                with gr.Row(equal_height=True):
                    prep_msg = gr.Textbox(
                        label="Your question",
                        placeholder="How should I talk about the AWS gap?",
                        lines=2,
                        scale=4,
                        elem_classes=["cc-field"],
                    )
                    prep_send_btn = gr.Button(
                        "Send",
                        variant="primary",
                        elem_classes=["cc-run"],
                        scale=0,
                        min_width=100,
                    )

            # ------------------------------------------------------------------ #
            # Tab 3 — Mock interview
            # ------------------------------------------------------------------ #
            with gr.Tab("3 · Mock interview"):
                gr.HTML(
                    "<div class='cc-panel-head'><h3>Voice mock interview</h3>"
                    "<p class='cc-hint'>Requires a finished Analyze first. The interviewer asks "
                    "questions from your resume and the role. Answer by voice or type. "
                    "Practice only — nothing is submitted.</p></div>"
                )
                with gr.Row():
                    iv_start_btn = gr.Button(
                        "Start interview",
                        variant="primary",
                        elem_classes=["cc-run"],
                        scale=0,
                        min_width=168,
                    )
                    iv_questions = gr.Slider(
                        minimum=3,
                        maximum=10,
                        value=_SETTINGS.interview_question_count,
                        step=1,
                        label="Number of questions",
                        scale=1,
                    )
                iv_error = gr.HTML("")
                iv_question_html = gr.HTML(_question_html(None, done=True))
                iv_audio = gr.Audio(
                    label="Interviewer (listen)",
                    autoplay=True,
                    interactive=False,
                    elem_id="cc-iv-audio",
                )
                with gr.Row(equal_height=True):
                    with gr.Column(scale=1):
                        gr.HTML("<div class='cc-section-title'>Your answer</div>")
                        iv_answer_audio = gr.Audio(
                            sources=["microphone"],
                            type="filepath",
                            label="Record your answer",
                        )
                        iv_answer_text = gr.Textbox(
                            label="Or type your answer",
                            placeholder="Type your answer if you prefer not to record…",
                            lines=4,
                            elem_classes=["cc-field"],
                        )
                        iv_submit_btn = gr.Button(
                            "Submit answer",
                            variant="primary",
                            elem_classes=["cc-run"],
                            scale=0,
                            min_width=168,
                        )
                    with gr.Column(scale=1):
                        gr.HTML("<div class='cc-section-title'>Live transcript</div>")
                        iv_chatbot = gr.Chatbot(
                            label="Interview transcript",
                            height=360,
                            elem_id="cc-iv-transcript",
                        )
                iv_feedback_html = gr.HTML("")
                iv_overall_html = gr.HTML("")

            # ------------------------------------------------------------------ #
            # Tab 4 — Post-interview coach
            # ------------------------------------------------------------------ #
            with gr.Tab("4 · Post-interview coach"):
                gr.HTML(
                    "<div class='cc-panel-head'><h3>Post-interview coach</h3>"
                    "<p class='cc-hint'>After your mock interview, ask about performance. "
                    "Remembers resume, JD, gaps, prep plan, and interview transcript.</p></div>"
                )
                post_chat = gr.Chatbot(label="Chat", height=380, show_label=False)
                with gr.Row(equal_height=True):
                    post_msg = gr.Textbox(
                        label="Your question",
                        placeholder="What should I improve before the real interview?",
                        lines=2,
                        scale=4,
                        elem_classes=["cc-field"],
                    )
                    post_send_btn = gr.Button(
                        "Send",
                        variant="primary",
                        elem_classes=["cc-run"],
                        scale=0,
                        min_width=100,
                    )

        gr.HTML(
            "<p class='cc-foot'>CareerCrew keeps everything honest — verified facts only, "
            "practice interviews that never submit anything, and anything uncertain left "
            "for you to answer.</p>"
        )

        # --- wiring --------------------------------------------------------- #
        named = {
            "error": error_box,
            "status": status,
            "stages": stages_html,
            "match_report": insight_html,
            "prep_plan": prep_html,
            "approve": approve_btn,
            "reject": reject_btn,
            "revise": revise_btn,
            "package": state,
            "notes": feedback,
            "context": ctx_state,
            "review_guide": review_guide_html,
            "run_button": run_btn,
            "clear_button": clear_btn,
        }
        analyze_outputs = [named[name] for name in OUTPUT_ORDER]

        decision_outputs = [
            review_guide_html,
            approve_btn,
            reject_btn,
            revise_btn,
            review_status,
            state,
            feedback,
        ]

        # show_progress="hidden": Gradio's default "full" mode draws an accent
        # border around every output for the whole run. This generator updates
        # 14 outputs, so those borders stack into stray blue rules. The stage
        # tracker below is the progress UI.
        run_btn.click(
            analyze,
            inputs=[resume_file, resume_text, jd_file, jd_text],
            outputs=analyze_outputs,
            show_progress="hidden",
        )

        clear_btn.click(
            lambda: (
                gr.update(value=None),
                gr.update(value=""),
                gr.update(value=None),
                gr.update(value=""),
                *_empty_outputs(),
            ),
            outputs=[
                resume_file, resume_text, jd_file, jd_text,
                *analyze_outputs,
            ],
        )

        sample_resume_btn.click(
            lambda: (gr.update(value=None), gr.update(value=_read_sample("sample_resume.txt"))),
            outputs=[resume_file, resume_text],
        )
        sample_jd_btn.click(
            lambda: (
                gr.update(value=None),
                gr.update(value=_read_sample("sample_jd.txt")),
            ),
            outputs=[jd_file, jd_text],
        )

        # --- mock interview wiring ------------------------------------------ #
        iv_start_btn.click(
            interview_start,
            inputs=[ctx_state, iv_questions],
            outputs=[
                iv_error, iv_question_html, iv_audio, iv_chatbot,
                iv_feedback_html, iv_overall_html, iv_state,
            ],
        )
        iv_submit_btn.click(
            interview_submit,
            inputs=[ctx_state, iv_state, iv_answer_text, iv_answer_audio],
            outputs=[
                iv_error, iv_question_html, iv_audio, iv_chatbot,
                iv_feedback_html, iv_overall_html, iv_state,
            ],
        )

        # --- coaching chat wiring (Enter or Send) --------------------------- #
        prep_msg.submit(
            _render_prep_chat,
            inputs=[prep_chat, prep_msg, ctx_state],
            outputs=[prep_chat, prep_msg],
        )
        prep_send_btn.click(
            _render_prep_chat,
            inputs=[prep_chat, prep_msg, ctx_state],
            outputs=[prep_chat, prep_msg],
        )
        post_msg.submit(
            _render_post_chat,
            inputs=[post_chat, post_msg, ctx_state, iv_state],
            outputs=[post_chat, post_msg],
        )
        post_send_btn.click(
            _render_post_chat,
            inputs=[post_chat, post_msg, ctx_state, iv_state],
            outputs=[post_chat, post_msg],
        )

        approve_btn.click(
            approve,
            inputs=[state, feedback],
            outputs=decision_outputs,
        )
        reject_btn.click(
            reject,
            inputs=[state, feedback],
            outputs=decision_outputs,
        )
        revise_btn.click(
            request_revision,
            inputs=[state, feedback],
            outputs=analyze_outputs,
            show_progress="hidden",
        )

    return demo


def theme() -> gr.themes.Base:
    """Clean light theme — simple blue accent, no fancy chrome."""
    # Do not pass plain string fonts: Gradio 6 compares Font objects on launch
    # and crashes with AttributeError if font entries are bare strings.
    return gr.themes.Default(
        primary_hue=gr.themes.colors.blue,
        secondary_hue=gr.themes.colors.blue,
        neutral_hue=gr.themes.colors.gray,
        radius_size=gr.themes.sizes.radius_sm,
    )


def main() -> None:
    """Launch the Gradio app bound to 0.0.0.0 for container deployment."""
    app = build_app()
    app.queue().launch(
        server_name="0.0.0.0",
        server_port=_SETTINGS.app_port,
        show_error=True,
        theme=theme(),
        css=CUSTOM_CSS,
        js=LIGHT_MODE_JS,
    )


if __name__ == "__main__":
    main()
