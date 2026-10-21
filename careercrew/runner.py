"""Background run of the analysis pipeline with live stage updates.

What it does: runs run_analysis on a worker thread and reports which stage is active.
Who calls it: the Analyze and Request-changes callbacks in app.py.
What it returns: yields (stage_index, detail) while running, then returns the PipelineResult.
"""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as wait_futures

from careercrew.pipeline import AnalysisRequest, PipelineResult, run_analysis

#: Candidate-facing progress steps. Numbers match the tracker in the UI.
STAGES: list[tuple[int, str, str]] = [
    (1, "Check inputs", "Make sure your resume and job posting look valid"),
    (2, "Read resume", "Pull out skills, roles, and achievements from your resume"),
    (3, "Understand role", "Extract what the job actually requires"),
    (4, "Score match", "Mark each requirement as covered, reframeable, or out of scope"),
    (5, "Draft rewrites", "Suggest stronger bullets backed by facts from your resume"),
    (6, "Prep plan", "Plan where to spend your interview preparation time"),
]
TOTAL_STAGES = len(STAGES)
FINAL_STAGE = TOTAL_STAGES + 1  # sentinel: marks every stage complete

#: Map CrewAI agent and task names onto a tracker step.
AGENT_STAGE = {
    "Profile Extractor": 2,
    "JD Analyzer": 3,
    "Gap Analyst": 4,
    "Feedback Writer": 5,
    "Interview Prep Advisor": 6,
}
TASK_STAGE = {
    "extract_profile": 2,
    "analyze_jd": 3,
    "analyze_gaps": 4,
    "write_feedback": 5,
    "build_prep_plan": 6,
}

# Names the UI already uses.
_TOTAL_STAGES = TOTAL_STAGES
_FINAL = FINAL_STAGE
_AGENT_STAGE = AGENT_STAGE
_TASK_STAGE = TASK_STAGE


def stream_with_progress(
    request: AnalysisRequest,
    *,
    stage_offset: int = 0,
    reading_detail: str = "Reading your resume…",
) -> Iterator[tuple[int, str]]:
    """Yield (stage_index, detail) as the pipeline reports progress.

    The generator's return value is the PipelineResult. Callers read it from
    ``StopIteration.value`` after the progress updates stop.
    ``stage_offset`` shifts every yielded index (0 for a normal Analyze run).
    """
    stages: dict[str, object] = {"index": 1, "detail": "Checking your inputs…"}

    def progress(message: str) -> None:
        lowered = message.lower()
        if "fallback" in lowered:
            stages["index"] = 6
            stages["detail"] = "Building a prep plan from the gaps…"
        elif "five-agent crew" in lowered:
            stages["index"] = 2
            stages["detail"] = reading_detail
        else:
            stages["detail"] = message

    def on_task(output) -> None:
        name = getattr(output, "name", "") or ""
        agent = getattr(output, "agent", "") or ""
        stage = AGENT_STAGE.get(agent) or TASK_STAGE.get(name)
        if stage:
            title = next((label for number, label, _ in STAGES if number == stage), name or agent)
            stages["index"] = stage + 1
            stages["detail"] = f"Finished: {title}"

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run_analysis, request, progress=progress, on_task=on_task)
        expected = 2
        last_yielded = 1
        while not future.done():
            reported = int(stages["index"])  # type: ignore[arg-type]
            if reported >= expected:
                expected = reported + 1
            target = min(expected, TOTAL_STAGES)
            if target != last_yielded:
                last_yielded = target
                detail = str(stages["detail"] or "Working…")
                yield target + stage_offset, detail
            wait_futures([future], timeout=1.0)
        result: PipelineResult = future.result()
    return result
