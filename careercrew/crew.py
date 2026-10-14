"""CareerCrew assembly (Day 2).

Standard CrewAI @CrewBase pattern: roles and task text live in YAML,
wiring (agents, tools, context, typed outputs) is explicit here so there
is no magic to debug. Process is sequential: the pipeline is linear
(extract -> analyze JD -> compare -> write), so no manager agent is needed.

Day 3 adds: knowledge base wiring, guardrail calls, HITL hook.
Day 4 swaps the @tool wrappers below for MCP-backed tools.
"""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from careercrew.models import (
    CandidateProfile,
    FeedbackDraft,
    GapReport,
    JobRequirements,
)
from careercrew.tools import fetch_jd_tool, read_resume_tool


@CrewBase
class CareerCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # --- agents ---

    @agent
    def profile_extractor(self) -> Agent:
        return Agent(
            config=self.agents_config["profile_extractor"],
            tools=[read_resume_tool],
        )

    @agent
    def jd_analyzer(self) -> Agent:
        return Agent(
            config=self.agents_config["jd_analyzer"],
            tools=[fetch_jd_tool],
        )

    @agent
    def gap_analyst(self) -> Agent:
        return Agent(config=self.agents_config["gap_analyst"])

    @agent
    def feedback_writer(self) -> Agent:
        return Agent(config=self.agents_config["feedback_writer"])

    # --- tasks (context wired explicitly: each task names its inputs) ---

    @task
    def extract_profile(self) -> Task:
        return Task(
            config=self.tasks_config["extract_profile"],
            agent=self.profile_extractor(),
            output_pydantic=CandidateProfile,
        )

    @task
    def analyze_jd(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_jd"],
            agent=self.jd_analyzer(),
            output_pydantic=JobRequirements,
        )

    @task
    def analyze_gaps(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_gaps"],
            agent=self.gap_analyst(),
            context=[self.extract_profile(), self.analyze_jd()],
            output_pydantic=GapReport,
        )

    @task
    def write_feedback(self) -> Task:
        return Task(
            config=self.tasks_config["write_feedback"],
            agent=self.feedback_writer(),
            context=[self.analyze_gaps()],
            output_pydantic=FeedbackDraft,
        )

    # --- crew ---

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            memory=True,  # short-term memory within a session (see ARCHITECTURE.md)
            verbose=True,
        )
