"""CareerCrew assembly.

Roles and task text live in ``config/agents.yaml`` and ``config/tasks.yaml``;
wiring (agents, MCP servers, knowledge, context, typed outputs) is explicit here
so there is no magic to debug. Process is sequential: the pipeline is linear
(extract -> analyze JD -> compare -> write -> package), so no manager agent is
needed.

The three tool-using agents are attached to the **real** CareerCrew MCP server
over stdio (``careercrew.mcp_client.crewai_mcp_server``), so ``read_resume``,
``fetch_job_description``, and ``query_answer_bank`` are genuine MCP calls.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml
from crewai import Agent, Crew, Process, Task
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

from careercrew.config import RESUME_GUIDELINES_PATH, get_settings
from careercrew.mcp_client import crewai_mcp_server
from careercrew.models import (
    ApplicationPackage,
    CandidateProfile,
    FeedbackDraft,
    GapReport,
    JobRequirements,
)

logger = logging.getLogger("careercrew.crew")

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
AGENTS_YAML = CONFIG_DIR / "agents.yaml"
TASKS_YAML = CONFIG_DIR / "tasks.yaml"


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _guidelines_source() -> StringKnowledgeSource:
    """Load the resume-writing guidelines as real agent knowledge.

    We pass the file *content* (not a path) so CrewAI does not depend on its
    working-directory-relative knowledge folder resolution.
    """
    content = RESUME_GUIDELINES_PATH.read_text(encoding="utf-8")
    return StringKnowledgeSource(
        content=content,
        metadata={"name": "resume_guidelines", "purpose": "writing and honesty rules"},
    )


def build_crew(*, verbose: bool = False) -> Crew:
    """Assemble the five agents and five tasks as a sequential crew."""
    settings = get_settings()
    if settings.openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    if settings.openai_base_url:
        os.environ.setdefault("OPENAI_BASE_URL", settings.openai_base_url)

    agents_cfg = _load_yaml(AGENTS_YAML)
    tasks_cfg = _load_yaml(TASKS_YAML)

    mcp_server = crewai_mcp_server()
    knowledge = _guidelines_source()

    def _agent(name: str, *, with_mcp: bool) -> Agent:
        kwargs = {
            "config": agents_cfg[name],
            "knowledge_sources": [knowledge],
            "verbose": verbose,
            "allow_delegation": False,
        }
        if with_mcp:
            kwargs["mcps"] = [mcp_server]
        return Agent(**kwargs)

    profile_extractor = _agent("profile_extractor", with_mcp=True)
    jd_analyzer = _agent("jd_analyzer", with_mcp=True)
    gap_analyst = _agent("gap_analyst", with_mcp=False)
    feedback_writer = _agent("feedback_writer", with_mcp=False)
    application_packager = _agent("application_packager", with_mcp=True)

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
    assemble_package = Task(
        name="assemble_package",
        config=tasks_cfg["assemble_package"],
        agent=application_packager,
        context=[write_feedback, analyze_jd],
        output_pydantic=ApplicationPackage,
    )

    return Crew(
        agents=[
            profile_extractor,
            jd_analyzer,
            gap_analyst,
            feedback_writer,
            application_packager,
        ],
        tasks=[extract_profile, analyze_jd, analyze_gaps, write_feedback, assemble_package],
        process=Process.sequential,
        memory=True,  # short-term memory within a session (see ARCHITECTURE.md)
        verbose=verbose,
    )


def crew_inputs(
    *,
    resume_path: str | None = None,
    resume_text: str | None = None,
    jd_source: str = "",
    screening_questions: str = "",
) -> dict:
    """Build the inputs mapping used by ``Crew.kickoff``.

    Exactly one of ``resume_path`` or ``resume_text`` is expected; the task text
    tells the agent which to use. ``jd_source`` is pasted text or an https URL.
    """
    if not resume_path and not resume_text:
        raise ValueError("provide either a resume file path or pasted resume text")
    return {
        "resume_path": resume_path or "(none; use pasted resume_text)",
        "resume_text": resume_text or "(none; use the read_resume tool)",
        "jd_source": jd_source,
        "screening_questions": screening_questions or "(none provided)",
    }


# Backwards-compatible alias: the original scaffold exposed ``CareerCrew().crew()``.
class CareerCrew:
    """Thin wrapper keeping the original ``CareerCrew().crew()`` entrypoint."""

    def crew(self, *, verbose: bool = True) -> Crew:
        return build_crew(verbose=verbose)
