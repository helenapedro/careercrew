"""Background run of the analysis pipeline with live stage updates.

What it does: runs run_analysis on a worker thread and reports which stage is active.
Who calls it: the Analyze and Request-changes callbacks.
What it returns: yields (stage_index, detail) while running, then returns the PipelineResult.
"""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as wait_futures
from enum import IntEnum

from careercrew.pipeline import AnalysisRequest, PipelineResult, run_analysis


class Stage(IntEnum):
    """The six steps shown on the Analyze progress tracker."""

    CHECK = 1
    RESUME = 2
    ROLE = 3
    MATCH = 4
    REWRITES = 5
    PREP = 6


#: Candidate-facing progress steps. Numbers match Stage.
STAGES: list[tuple[int, str, str]] = [
    (Stage.CHECK, "Check inputs", "Make sure your resume and job posting look valid"),
    (Stage.RESUME, "Read resume", "Pull out skills, roles, and achievements from your resume"),
    (Stage.ROLE, "Understand role", "Extract what the job actually requires"),
    (Stage.MATCH, "Score match", "Mark each requirement as covered, reframeable, or out of scope"),
    (Stage.REWRITES, "Draft rewrites", "Suggest stronger bullets backed by facts from your resume"),
    (Stage.PREP, "Prep plan", "Plan where to spend your interview preparation time"),
]
TOTAL_STAGES = len(STAGES)
FINAL_STAGE = int(Stage.PREP) + 1  # sentinel: marks every stage complete

#: Map CrewAI agent and task names onto a tracker step.
AGENT_STAGE = {
    "Profile Extractor": Stage.RESUME,
    "JD Analyzer": Stage.ROLE,
    "Gap Analyst": Stage.MATCH,
    "Feedback Writer": Stage.REWRITES,
    "Interview Prep Advisor": Stage.PREP,
}
TASK_STAGE = {
    "extract_profile": Stage.RESUME,
    "analyze_jd": Stage.ROLE,
    "analyze_gaps": Stage.MATCH,
    "write_feedback": Stage.REWRITES,
    "build_prep_plan": Stage.PREP,
}


def stream_with_progress(
    request: AnalysisRequest,
    *,
    reading_detail: str = "Reading your resume…",
) -> Iterator[tuple[int, str]]:
    """Yield (stage_index, detail) as the pipeline reports progress.

    The generator's return value is the PipelineResult. Callers read it from
    ``StopIteration.value`` after the progress updates stop.
    """
    stages: dict[str, object] = {"index": Stage.CHECK, "detail": "Checking your inputs…"}

    def progress(message: str) -> None:
        lowered = message.lower()
        if "fallback" in lowered:
            stages["index"] = Stage.PREP
            stages["detail"] = "Building a prep plan from the gaps…"
        elif "five-agent crew" in lowered:
            stages["index"] = Stage.RESUME
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
                yield target, detail
            wait_futures([future], timeout=1.0)
        result: PipelineResult = future.result()
    return result
