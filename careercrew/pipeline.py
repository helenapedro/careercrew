"""CareerCrew - the analysis pipeline (orchestrator).

This module runs the whole analysis for one request:

1. Validate input (input guardrails).
2. Run the six-agent CrewAI crew (off the event loop so the UI stays responsive).
3. Parse the agents' JSON into typed models, with bounded repair.
4. If the crew output cannot be parsed, fall back to a deterministic path that
   makes the **same** real MCP calls directly, so the run still yields grounded
   screening answers (never fabricated) and is honest about what happened.
5. Validate the assembled outputs (output guardrails) - fail closed.

Every step is recorded in an :class:`~careercrew.models.ExecutionTrace`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from careercrew import guardrails
from careercrew.config import Settings, get_settings
from careercrew.document_tools import (
    JobDescriptionError,
    read_job_description,
    read_resume,
    read_resume_text,
)
from careercrew.mcp_client import MCPToolClient
from careercrew.models import (
    CandidateProfile,
    ExecutionTrace,
    FeedbackDraft,
    GapReport,
    InterviewPrepPlan,
    JobRequirements,
    ScreeningAnswer,
    ScreeningPrep,
)

logger = logging.getLogger("careercrew.pipeline")

ProgressFn = Callable[[str], None]
#: Optional per-task callback (receives a crewai ``TaskOutput`` after each task).
TaskCallback = Callable[[Any], None]

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


@dataclass
class AnalysisRequest:
    """Normalized inputs for one analysis run."""

    package_id: str
    resume_path: str | None = None
    resume_text: str | None = None
    jd_path: str | None = None
    jd_text: str | None = None
    screening_questions: list[str] = field(default_factory=list)
    seniority: str = ""


@dataclass
class PipelineResult:
    """Everything produced by one analysis run."""

    package: ScreeningPrep
    profile: CandidateProfile
    requirements: JobRequirements
    gaps: GapReport
    feedback: FeedbackDraft
    trace: ExecutionTrace
    request: AnalysisRequest
    prep_plan: InterviewPrepPlan = field(default_factory=InterviewPrepPlan)
    warnings: list[str] = field(default_factory=list)
    used_fallback: bool = False


#: The crew's task order. Used to map task outputs onto pipeline stages.
CREW_STAGES = [
    "profile",
    "requirements",
    "gaps",
    "feedback",
    "prep_plan",
    "package",
]


# --------------------------------------------------------------------------- #
# JSON helpers
# --------------------------------------------------------------------------- #
def extract_json(raw: str | None) -> Any | None:
    """Best-effort extraction of a JSON object/array from model text."""
    if not raw:
        return None
    text = raw.strip()
    fenced = _FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except (ValueError, TypeError):
                continue
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [value]


def _coerce_model(model_cls, data: Any):
    """Validate model data, returning None when it cannot be coerced."""
    if isinstance(data, dict):
        try:
            return model_cls.model_validate(data)
        except Exception:  # noqa: BLE001 - bounded repair, never crash
            return None
    return None


# --------------------------------------------------------------------------- #
# Deterministic MCP fallback
# --------------------------------------------------------------------------- #
def deterministic_package(
    request: AnalysisRequest, trace: ExecutionTrace, mcp: MCPToolClient
) -> ScreeningPrep:
    """Assemble copy-ready screening answers with direct real MCP calls.

    Used only when the crew output cannot be parsed. Every call is a genuine MCP
    call and is recorded in the trace; unknown questions go to do_not_claim.
    """
    answers: list[ScreeningAnswer] = []
    do_not_claim: list[str] = []
    for question in request.screening_questions:
        started = time.perf_counter()
        payload = mcp.query_answer_bank(question)
        trace.add(
            "mcp.call.query_answer_bank",
            "pipeline",
            f"{question[:60]} -> {payload.get('status')}",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        if isinstance(payload, dict) and payload.get("found"):
            answers.append(
                ScreeningAnswer(
                    question=question,
                    answer=str(payload.get("answer", "")),
                    source="answer_bank",
                    verified=True,
                )
            )
        else:
            do_not_claim.append(question)

    return ScreeningPrep(
        package_id=request.package_id,
        role_title="",
        company="",
        screening_answers=answers,
        package_summary=(
            "Copy-ready screening answers assembled from the verified answer bank. "
            "Nothing is submitted on your behalf. Questions without a verified entry "
            "are listed under do_not_claim."
        ),
        do_not_claim=do_not_claim,
    )


#: Backwards-compatible alias for the deterministic fallback.
deterministic_screening_prep = deterministic_package


def _parse_package(data: Any, package_id: str) -> ScreeningPrep | None:
    """Map the screening-prep task JSON onto a ScreeningPrep with bounded repair."""
    if not isinstance(data, dict):
        return None
    answers: list[ScreeningAnswer] = []
    for item in _as_list(data.get("screening_answers")):
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        source = str(item.get("source") or "answer_bank").strip() or "answer_bank"
        if not question or not answer:
            continue
        answers.append(
            ScreeningAnswer(
                question=question,
                answer=answer,
                source=source,
                verified=bool(item.get("verified", True)),
            )
        )
    return ScreeningPrep(
        package_id=package_id,
        role_title=str(data.get("role_title") or ""),
        company=str(data.get("company") or ""),
        screening_answers=answers,
        package_summary=str(data.get("package_summary") or ""),
        do_not_claim=[str(item) for item in _as_list(data.get("do_not_claim"))],
    )


# --------------------------------------------------------------------------- #
# Crew execution
# --------------------------------------------------------------------------- #
def _prepare_resume_text(request: AnalysisRequest) -> str:
    """Resolve the resume to plain text (file read or pasted)."""
    if request.resume_text:
        return read_resume_text(request.resume_text)
    if request.resume_path:
        return read_resume(request.resume_path)
    raise ValueError("no resume provided")


def _prepare_jd_text(request: AnalysisRequest) -> str:
    """Resolve the job description to plain text (file read or pasted)."""
    if request.jd_path:
        return read_job_description(request.jd_path)
    if request.jd_text:
        return read_job_description(request.jd_text)
    raise ValueError("no job description provided")


def _run_crew(
    request: AnalysisRequest,
    trace: ExecutionTrace,
    notify: ProgressFn,
    on_task: TaskCallback | None = None,
):
    from careercrew.crew import build_crew, crew_inputs

    inputs = crew_inputs(
        resume_path=request.resume_path if not request.resume_text else None,
        resume_text=request.resume_text,
        jd_path=request.jd_path if not request.jd_text else None,
        jd_text=request.jd_text,
        screening_questions="\n".join(request.screening_questions) or "(none provided)",
        seniority=request.seniority or "2-3 years",
    )
    started = time.perf_counter()
    crew = build_crew(verbose=False, on_task=on_task)
    result = asyncio.run(asyncio.to_thread(crew.kickoff, inputs=inputs))
    trace.add(
        "crew.kickoff",
        "crew",
        "six agents completed",
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return result


def _parse_crew_outputs(result: Any, request: AnalysisRequest, trace: ExecutionTrace) -> dict:
    outputs = list(getattr(result, "tasks_output", []) or [])
    parsed: dict[str, Any] = {}
    for stage, output in zip(CREW_STAGES, outputs, strict=False):
        parsed[stage] = extract_json(getattr(output, "raw", None))
    trace.add("crew.parsed", "pipeline", f"{len(outputs)} task outputs parsed")

    profile = _coerce_model(CandidateProfile, parsed.get("profile"))
    requirements = _coerce_model(JobRequirements, parsed.get("requirements"))
    gaps = _coerce_model(GapReport, parsed.get("gaps"))
    feedback = _coerce_model(FeedbackDraft, parsed.get("feedback"))
    prep_plan = _coerce_model(InterviewPrepPlan, parsed.get("prep_plan"))
    package = _parse_package(parsed.get("package"), request.package_id)
    return {
        "profile": profile,
        "requirements": requirements,
        "gaps": gaps,
        "feedback": feedback,
        "prep_plan": prep_plan,
        "package": package,
    }


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def run_analysis(
    request: AnalysisRequest,
    *,
    settings: Settings | None = None,
    progress: ProgressFn | None = None,
    on_task: TaskCallback | None = None,
    allow_fallback: bool = True,
) -> PipelineResult:
    """Run the full analysis for ``request`` and return a validated package.

    ``progress`` receives short human-readable status strings; ``on_task`` is an
    optional per-task callback used by the UI to show which agent is executing.
    """
    settings = settings or get_settings()
    trace = ExecutionTrace()
    warnings: list[str] = []

    def notify(message: str) -> None:
        if progress:
            try:
                progress(message)
            except Exception:  # pragma: no cover - progress must never break the run
                logger.debug("progress callback failed", exc_info=True)

    # 1. Input guardrails.
    check = guardrails.validate_request(
        resume_path=request.resume_path,
        resume_text=request.resume_text,
        jd_path=request.jd_path,
        jd_text=request.jd_text,
        screening_questions=request.screening_questions,
    )
    if not check.ok:
        trace.add("guardrail.input", "guardrails", "; ".join(check.errors), status="error")
        raise ValueError("; ".join(check.errors))
    trace.add("guardrail.input", "guardrails", "inputs accepted")

    # Normalize the resume and JD to text up front so a bad file fails fast with
    # a clear error instead of failing deep inside the crew. The crew re-reads a
    # file through MCP, and uses pasted text directly.
    try:
        _prepare_resume_text(request)
    except JobDescriptionError:
        raise
    except Exception as exc:  # noqa: BLE001
        trace.add("input.resume", "pipeline", f"{type(exc).__name__}: {exc}", status="error")
        raise ValueError(f"Could not read the resume: {exc}") from exc

    # Validate the JD here so the error surfaces before the crew. Call the
    # document tool directly (not through MCP) so the original
    # JobDescriptionError message is preserved for the UI.
    try:
        _prepare_jd_text(request)
        trace.add("input.jd", "pipeline", "job description read")
    except JobDescriptionError as exc:
        trace.add("input.jd", "pipeline", str(exc), status="error")
        raise
    except Exception as exc:  # noqa: BLE001
        trace.add("input.jd", "pipeline", f"{type(exc).__name__}: {exc}", status="error")
        raise JobDescriptionError(
            "The job description could not be read. Upload a PDF/DOCX/TXT file "
            "or paste the job description text instead."
        ) from exc

    # 2/3. Run the crew and parse typed outputs; fall back if needed.
    profile: CandidateProfile | None = None
    requirements: JobRequirements | None = None
    gaps: GapReport | None = None
    feedback: FeedbackDraft | None = None
    prep_plan: InterviewPrepPlan | None = None
    package: ScreeningPrep | None = None
    used_fallback = False

    if settings.has_llm:
        notify("Running the six-agent crew (this can take a minute)...")
        try:
            crew_result = _run_crew(request, trace, notify, on_task)
            parsed = _parse_crew_outputs(crew_result, request, trace)
            profile = parsed["profile"]
            requirements = parsed["requirements"]
            gaps = parsed["gaps"]
            feedback = parsed["feedback"]
            prep_plan = parsed["prep_plan"]
            package = parsed["package"]
        except Exception as exc:  # noqa: BLE001 - degrade gracefully, never crash the UI
            logger.warning("crew run failed: %s", exc)
            trace.add("crew.error", "crew", f"{type(exc).__name__}: {exc}", status="error")
            warnings.append("The agent crew did not complete; using the MCP fallback.")
    else:
        warnings.append("No OPENAI_API_KEY set; running the deterministic MCP fallback only.")

    if package is None and allow_fallback:
        used_fallback = True
        notify("Crew output unavailable - preparing screening answers via direct MCP calls...")
        mcp = MCPToolClient(timeout_s=settings.request_timeout_s)
        try:
            package = deterministic_package(request, trace, mcp)
        except Exception as exc:  # noqa: BLE001
            trace.add("mcp.error", "pipeline", f"{type(exc).__name__}: {exc}", status="error")
            warnings.append("MCP fallback failed; no screening answers could be assembled.")
            package = ScreeningPrep(package_id=request.package_id)

    # Ensure the package carries the id and any do_not_claim from the feedback.
    assert package is not None
    package.package_id = package.package_id or request.package_id
    if feedback and feedback.do_not_claim:
        for item in feedback.do_not_claim:
            if item not in package.do_not_claim:
                package.do_not_claim.append(item)

    # Build a deterministic prep plan when the crew did not produce one, so the
    # Interview Prep tab always has grounded, gap-derived guidance.
    if prep_plan is None:
        from careercrew.prep import build_fallback_plan

        prep_plan = build_fallback_plan(
            profile or CandidateProfile(),
            requirements or JobRequirements(),
            gaps or GapReport(),
            request.seniority,
        )
        if settings.has_llm:
            warnings.append("Interview prep plan used the deterministic gap-based fallback.")

    # 4. Output guardrails (fail closed).
    validation = guardrails.validate_package(package, feedback, profile)
    warnings.extend(validation.warnings)
    if not validation.ok:
        trace.add("guardrail.output", "guardrails", "; ".join(validation.errors), status="error")
        raise ValueError("Screening prep failed output guardrails: " + "; ".join(validation.errors))
    trace.add("guardrail.output", "guardrails", "screening prep validated")

    plan_problems = guardrails.validate_prep_plan(prep_plan, gaps or GapReport(), requirements)
    if plan_problems:
        trace.add(
            "guardrail.prep", "guardrails", "; ".join(plan_problems), status="warning"
        )
        warnings.extend(plan_problems)
    else:
        trace.add("guardrail.prep", "guardrails", "prep plan validated")

    if used_fallback:
        warnings.append("Run used the deterministic MCP fallback instead of the agent crew.")

    return PipelineResult(
        package=package,
        profile=profile or CandidateProfile(),
        requirements=requirements or JobRequirements(),
        gaps=gaps or GapReport(),
        feedback=feedback or FeedbackDraft(),
        prep_plan=prep_plan,
        trace=trace,
        request=request,
        warnings=warnings,
        used_fallback=used_fallback,
    )


def make_package_id() -> str:
    """Generate a short unique package identifier."""
    return f"pkg-{uuid.uuid4().hex[:8]}"
