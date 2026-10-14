"""Pydantic output contracts for every crew task.

Typed outputs are the backbone of the honesty guarantee: downstream agents
and guardrails consume these models, not free text, so a missing fact is a
missing field instead of an invented sentence.
"""

from pydantic import BaseModel, Field


class WorkExperience(BaseModel):
    company: str = ""
    title: str = ""
    dates: str = ""
    achievements: list[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    full_name: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[WorkExperience] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)


class JobRequirements(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    seniority: str = ""
    nice_to_have: list[str] = Field(default_factory=list)


class GapVerdict(BaseModel):
    requirement: str
    verdict: str = Field(description="one of: covered, reframeable, out_of_scope")
    supporting_fact: str = ""


class GapReport(BaseModel):
    coverage_score: int = Field(ge=0, le=100)
    verdicts: list[GapVerdict] = Field(default_factory=list)


class RewrittenBullet(BaseModel):
    text: str
    cited_fact: str = Field(description="profile fact this bullet is based on")


class FeedbackDraft(BaseModel):
    rewritten_bullets: list[RewrittenBullet] = Field(default_factory=list)
    talking_points: list[str] = Field(default_factory=list)
    do_not_claim: list[str] = Field(default_factory=list)
