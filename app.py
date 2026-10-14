"""Gradio UI shell (Day 2/3). Run: python app.py

Day 3 extends this with the real HITL approval screen and guardrail wiring.
"""

import os
import shutil

import gradio as gr
from dotenv import load_dotenv

from careercrew.crew import CareerCrew
from careercrew.guardrails import check_upload, redact_pii

load_dotenv()
UPLOAD_DIR = os.environ.get("CAREERCREW_UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def run_crew(resume_file, jd_text):
    if resume_file is None:
        return "Upload a resume file first.", "", ""
    if not (jd_text or "").strip():
        return "Paste a job description or URL first.", "", ""
    check_upload(resume_file)
    resume_path = os.path.join(UPLOAD_DIR, os.path.basename(resume_file))
    shutil.copyfile(resume_file, resume_path)

    crew = CareerCrew().crew()
    result = crew.kickoff(
        inputs={"resume_path": resume_path, "jd_source": redact_pii(jd_text)}
    )

    gap_json, feedback_json = "", ""
    try:
        for task_output in result.tasks_output:
            name = task_output.name or ""
            try:
                dumped = task_output.pydantic.model_dump_json(indent=2)
            except Exception:
                dumped = str(task_output)
            if "gap" in name:
                gap_json = dumped
            elif "feedback" in name:
                feedback_json = dumped
    except Exception:
        pass
    return str(result), gap_json, feedback_json


def approve_feedback(edits):
    # TODO (Day 3): persist approval, re-run citation check on edited text.
    note = "Approved." if not (edits or "").strip() else "Approved with your edits."
    return note + " (stub: Day 3 wires persistence and re-validation here)"


with gr.Blocks(title="CareerCrew") as demo:
    gr.Markdown("# CareerCrew: multi-agent resume coach")
    with gr.Row():
        resume_in = gr.File(label="Resume (PDF or TXT)", file_types=[".pdf", ".txt"])
        jd_in = gr.Textbox(label="Job description (paste text or https URL)", lines=10)
    run_btn = gr.Button("Run analysis", variant="primary")
    summary_out = gr.Textbox(label="Result summary", lines=12)
    with gr.Row():
        gap_out = gr.Code(label="Gap report (JSON)", language="json")
        feedback_out = gr.Code(label="Feedback draft (JSON)", language="json")
    with gr.Row():
        edits_in = gr.Textbox(label="Your edits (optional)", lines=4)
        approve_btn = gr.Button("Approve final bullets")
    approval_out = gr.Textbox(label="HITL status")

    run_btn.click(run_crew, inputs=[resume_in, jd_in],
                  outputs=[summary_out, gap_out, feedback_out])
    approve_btn.click(approve_feedback, inputs=[edits_in], outputs=[approval_out])

if __name__ == "__main__":
    demo.launch()
