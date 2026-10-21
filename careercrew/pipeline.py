"""CareerCrew - the analysis pipeline (orchestrator).

This module runs the whole analysis for one request:

1. Validate input (input guardrails).
2. Run the five-agent CrewAI crew (off the event loop so the UI stays responsive).
3. Parse the agents' JSON into typed models, with bounded repair.
4. If the crew does not finish, still return a grounded prep plan from the gaps.
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
from careercrew.models import (
    ApplicationPackage,
    CandidateProfile,
    ExecutionTrace,
    FeedbackDraft,
    GapReport,
    GapVerdict,
    InterviewPrepPlan,
    JobRequirements,
    RewrittenBullet,
    WorkExperience,
    infer_seniority_from_jd,
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
    seniority: str = ""
    #: Human HITL notes from "Request changes" — empty on the first Analyze.
    revision_notes: str = ""


@dataclass
class PipelineResult:
    """Everything produced by one analysis run."""

    package: ApplicationPackage
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


def _apply_revision_experience(
    profile: CandidateProfile | None,
    gaps: GapReport | None,
    requirements: JobRequirements | None,
    request: AnalysisRequest,
) -> tuple[CandidateProfile, GapReport, JobRequirements]:
    """Fold Request-changes notes into profile/gaps when the crew did not.

    Used so offline / fallback runs still treat candidate-attested experience
    (e.g. React years) as covering matching JD requirements.
    """
    profile = profile or CandidateProfile()
    gaps = gaps or GapReport()
    requirements = requirements or JobRequirements()
    notes = (request.revision_notes or "").strip()
    if not notes:
        return profile, gaps, requirements

    already = any(
        "candidate-attested" in (role.company or "").lower()
        or notes[:80] in " ".join(role.achievements)
        for role in profile.experience
    )
    if not already:
        profile.experience.append(
            WorkExperience(
                company="Candidate-attested update",
                title="Additional experience (Request changes)",
                achievements=[notes],
            )
        )

    notes_l = notes.lower()
    # Promote out-of-scope / missing requirements that the notes clearly cover.
    updated: list[GapVerdict] = []
    seen_reqs: set[str] = set()
    for verdict in gaps.verdicts:
        seen_reqs.add(verdict.requirement.lower())
        req_l = verdict.requirement.lower()
        tokens = [t for t in re.findall(r"[a-zA-Z][a-zA-Z0-9+.#]{2,}", req_l) if t not in {"and", "the", "with", "for"}]
        if verdict.verdict == "out_of_scope" and any(tok in notes_l for tok in tokens):
            updated.append(
                GapVerdict(
                    requirement=verdict.requirement,
                    verdict="covered",
                    supporting_fact=notes[:240],
                )
            )
        else:
            updated.append(verdict)

    skill_pool = list(requirements.required_skills) + list(requirements.keywords)
    if not skill_pool and (request.jd_text or "").strip():
        # Offline path often has no structured JD yet — pull tokens that appear
        # in both the posting and the candidate's attested notes.
        jd_l = request.jd_text.lower()
        for tok in sorted(set(re.findall(r"[a-zA-Z][a-zA-Z0-9+.#]{2,}", notes_l)), key=len, reverse=True):
            if len(tok) < 4 or tok in {"have", "years", "year", "with", "experience", "building"}:
                continue
            if tok in jd_l:
                skill_pool.append(tok)

    for skill in skill_pool:
        key = (skill or "").strip()
        if not key or key.lower() in seen_reqs:
            continue
        if key.lower() in notes_l:
            updated.append(
                GapVerdict(
                    requirement=key,
                    verdict="covered",
                    supporting_fact=notes[:240],
                )
            )
            seen_reqs.add(key.lower())
            if key not in requirements.required_skills and key not in requirements.keywords:
                requirements.keywords.append(key)

    if updated:
        gaps.verdicts = updated
        covered = sum(1 for v in updated if (v.verdict or "").lower() == "covered")
        if updated:
            gaps.coverage_score = max(gaps.coverage_score, round(100 * covered / len(updated)))

    return profile, gaps, requirements


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
        seniority=(
            request.seniority
            or "the seniority / years of experience signaled in the job description"
        ),
        revision_notes=(request.revision_notes or "").strip()
        or "(none — produce the initial package)",
    )
    started = time.perf_counter()
    crew = build_crew(verbose=False, on_task=on_task)
    result = asyncio.run(asyncio.to_thread(crew.kickoff, inputs=inputs))
    trace.add(
        "crew.kickoff",
        "crew",
        "five agents completed",
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
    return {
        "profile": profile,
        "requirements": requirements,
        "gaps": gaps,
        "feedback": feedback,
        "prep_plan": prep_plan,
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
        jd_plain = _prepare_jd_text(request)
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

    # Seniority comes from the job description (not a UI picker). Optional
    # request.seniority remains as a CLI override when explicitly provided.
    if not (request.seniority or "").strip():
        request.seniority = infer_seniority_from_jd(jd_plain)
        if request.seniority:
            trace.add(
                "input.seniority",
                "pipeline",
                f"inferred from JD: {request.seniority}",
            )

    # 2/3. Run the crew and parse typed outputs; fall back if needed.
    profile: CandidateProfile | None = None
    requirements: JobRequirements | None = None
    gaps: GapReport | None = None
    feedback: FeedbackDraft | None = None
    prep_plan: InterviewPrepPlan | None = None
    package: ApplicationPackage | None = None
    used_fallback = False

    if settings.has_llm:
        notify("Running the five-agent crew (this can take a minute)...")
        try:
            crew_result = _run_crew(request, trace, notify, on_task)
            parsed = _parse_crew_outputs(crew_result, request, trace)
            profile = parsed["profile"]
            requirements = parsed["requirements"]
            gaps = parsed["gaps"]
            feedback = parsed["feedback"]
            prep_plan = parsed["prep_plan"]
        except Exception as exc:  # noqa: BLE001 - degrade gracefully, never crash the UI
            logger.warning("crew run failed: %s", exc)
            trace.add("crew.error", "crew", f"{type(exc).__name__}: {exc}", status="error")
            warnings.append("The agent crew did not complete; using the gap-based fallback.")
            used_fallback = True
    else:
        warnings.append("No OPENAI_API_KEY set; running the gap-based fallback only.")
        used_fallback = True

    if package is None:
        package = ApplicationPackage(package_id=request.package_id)
        if not settings.has_llm:
            used_fallback = True

    # Ensure the package carries the id and any do_not_claim from the feedback.
    assert package is not None
    package.package_id = package.package_id or request.package_id
    if feedback and feedback.do_not_claim:
        for item in feedback.do_not_claim:
            if item not in package.do_not_claim:
                package.do_not_claim.append(item)

    # Candidate-attested Request-changes notes enrich profile/gaps (especially
    # important on the offline fallback path where the crew did not re-score).
    if (request.revision_notes or "").strip():
        profile, gaps, requirements = _apply_revision_experience(
            profile, gaps, requirements, request
        )
        if feedback is None:
            feedback = FeedbackDraft(
                rewritten_bullets=[
                    RewrittenBullet(
                        text=f"Highlight attested experience: {(request.revision_notes or '')[:180]}",
                        cited_fact=(request.revision_notes or "")[:240],
                    )
                ],
                talking_points=[
                    f"Be ready to discuss: {(request.revision_notes or '')[:160]}",
                ],
            )
        warnings.append("Candidate-attested Request changes updates were applied to experience.")

    # Build a deterministic prep plan when the crew did not produce one, so the
    # Interview Prep tab always has grounded, gap-derived guidance.
    if prep_plan is None:
        from careercrew.prep import build_fallback_plan

        # Prefer JD-extracted requirements.seniority when the crew produced it.
        reqs = requirements or JobRequirements()
        effective_seniority = (reqs.seniority or request.seniority or "").strip()
        prep_plan = build_fallback_plan(
            profile or CandidateProfile(),
            reqs,
            gaps or GapReport(),
            effective_seniority,
        )
        if settings.has_llm:
            warnings.append("Interview prep plan used the deterministic gap-based fallback.")

    # 4. Output guardrails (fail closed).
    validation = guardrails.validate_package(package, feedback, profile)
    warnings.extend(validation.warnings)
    if not validation.ok:
        trace.add("guardrail.output", "guardrails", "; ".join(validation.errors), status="error")
        raise ValueError("Prep bundle failed output guardrails: " + "; ".join(validation.errors))
    trace.add("guardrail.output", "guardrails", "prep bundle validated")

    plan_problems = guardrails.validate_prep_plan(prep_plan, gaps or GapReport(), requirements)
    if plan_problems:
        trace.add(
            "guardrail.prep", "guardrails", "; ".join(plan_problems), status="warning"
        )
        warnings.extend(plan_problems)
    else:
        trace.add("guardrail.prep", "guardrails", "prep plan validated")

    if used_fallback:
        warnings.append("Run used the gap-based fallback instead of the agent crew.")

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
