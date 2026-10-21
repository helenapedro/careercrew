"""Build the five-agent crew from the YAML role and task files.

What it does: creates the agents and tasks and connects the MCP document tools.
Who calls it: pipeline._run_crew, once per Analyze click.
What it returns: a sequential CrewAI crew, plus the kickoff input dict.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml
from crewai import Agent, Crew, Process, Task
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

from careercrew.config import (
    INTERVIEW_GUIDELINES_PATH,
    RESUME_GUIDELINES_PATH,
    get_settings,
)
from careercrew.mcp_client import crewai_mcp_server
from careercrew.models import (
    CandidateProfile,
    FeedbackDraft,
    GapReport,
    InterviewPrepPlan,
    JobRequirements,
)

logger = logging.getLogger("careercrew.crew")

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
AGENTS_YAML = CONFIG_DIR / "agents.yaml"
TASKS_YAML = CONFIG_DIR / "tasks.yaml"


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _guidelines_source(path: Path, name: str) -> StringKnowledgeSource:
    """Load a guidelines file as real agent knowledge.

    We pass the file *content* (not a path) so CrewAI does not depend on its
    working-directory-relative knowledge folder resolution.
    """
    content = path.read_text(encoding="utf-8")
    return StringKnowledgeSource(
        content=content,
        metadata={"name": name, "purpose": "writing, prep, and honesty rules"},
    )


def build_crew(*, verbose: bool = False, on_task=None, on_step=None) -> Crew:
    """Assemble the five agents and five tasks as a sequential crew.

    ``on_task`` / ``on_step`` are optional callbacks: ``on_task`` is called with
    the :class:`~crewai.tasks.task_output.TaskOutput` after each of the five
    tasks finishes, and ``on_step`` after each agent step. They power the live
    stage tracker in the UI and are never required.
    """
    settings = get_settings()
    if settings.openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    if settings.openai_base_url:
        os.environ.setdefault("OPENAI_BASE_URL", settings.openai_base_url)

    agents_cfg = _load_yaml(AGENTS_YAML)
    tasks_cfg = _load_yaml(TASKS_YAML)

    mcp_server = crewai_mcp_server()
    knowledge = _guidelines_source(RESUME_GUIDELINES_PATH, "resume_guidelines")
    interview_knowledge = _guidelines_source(
        INTERVIEW_GUIDELINES_PATH, "interview_guidelines"
    )

    def _agent(name: str, *, with_mcp: bool, extra_knowledge=None) -> Agent:
        sources = [knowledge]
        if extra_knowledge is not None:
            sources.append(extra_knowledge)
        kwargs = {
            "config": agents_cfg[name],
            "knowledge_sources": sources,
            "verbose": verbose,
            "allow_delegation": False,
        }
        if with_mcp:
            kwargs["mcps"] = [mcp_server]
        if on_step is not None:
            kwargs["step_callback"] = on_step
        return Agent(**kwargs)

    profile_extractor = _agent("profile_extractor", with_mcp=True)
    jd_analyzer = _agent("jd_analyzer", with_mcp=True)
    gap_analyst = _agent("gap_analyst", with_mcp=False)
    feedback_writer = _agent("feedback_writer", with_mcp=False)
    interview_prep_advisor = _agent(
        "interview_prep_advisor", with_mcp=False, extra_knowledge=interview_knowledge
    )
    extract_profile = Task(
        name="extract_profile",
        config=tasks_cfg["extract_profile"],
        agent=profile_extractor,
        output_pydantic=CandidateProfile,
    )
    analyze_jd = Task(
        name="analyze_jd",
        config=tasks_cfg["analyze_jd"],
        agent=jd_analyzer,
        output_pydantic=JobRequirements,
    )
    analyze_gaps = Task(
        name="analyze_gaps",
        config=tasks_cfg["analyze_gaps"],
        agent=gap_analyst,
        context=[extract_profile, analyze_jd],
        output_pydantic=GapReport,
    )
    write_feedback = Task(
        name="write_feedback",
        config=tasks_cfg["write_feedback"],
        agent=feedback_writer,
        context=[analyze_gaps],
        output_pydantic=FeedbackDraft,
    )
    build_prep_plan = Task(
        name="build_prep_plan",
        config=tasks_cfg["build_prep_plan"],
        agent=interview_prep_advisor,
        context=[extract_profile, analyze_jd, analyze_gaps],
        output_pydantic=InterviewPrepPlan,
    )

    return Crew(
        agents=[
            profile_extractor,
            jd_analyzer,
            gap_analyst,
            feedback_writer,
            interview_prep_advisor,
        ],
        tasks=[
            extract_profile,
            analyze_jd,
            analyze_gaps,
            write_feedback,
            build_prep_plan,
        ],
        process=Process.sequential,
        memory=True,  # short-term memory within a session (see ARCHITECTURE.md)
        verbose=verbose,
        task_callback=on_task,
        step_callback=on_step,
    )


def crew_inputs(
    *,
    resume_path: str | None = None,
    resume_text: str | None = None,
    jd_path: str | None = None,
    jd_text: str | None = None,
    seniority: str = "",
    revision_notes: str = "",
) -> dict:
    """Build the inputs mapping used by ``Crew.kickoff``.

    Exactly one of ``resume_path`` / ``resume_text`` and one of ``jd_path`` /
    ``jd_text`` is expected; the task text tells the agent which to use.
    """
    if not resume_path and not resume_text:
        raise ValueError("provide either a resume file path or pasted resume text")
    if not jd_path and not jd_text:
        raise ValueError("provide either a JD file path or pasted JD text")
    return {
        "resume_path": resume_path or "(none; use pasted resume_text)",
        "resume_text": resume_text or "(none; use the read_resume tool)",
        "jd_path": jd_path or "(none; use pasted jd_text)",
        "jd_text": jd_text or "(none; use the read_job_description tool)",
        "seniority": seniority
        or "the seniority / years of experience signaled in the job description",
        "revision_notes": revision_notes
        or "(none — produce the initial package)",
    }


