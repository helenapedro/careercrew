# Agents and Workflows

## 1. Agent Roles and Tasks

The roles below are the five agents the crew actually runs. Their prompts live in
`config/agents.yaml`; their task text and expected output live in `config/tasks.yaml`.
`careercrew/crew.py` wires the two files together.

| Agent / role | Inputs | Responsibilities | Expected output | Guardrails |
|---|---|---|---|---|
| 1. Profile Extractor | Resume file or pasted resume text, read through the MCP `read_resume_tool` | Extract skills, roles, dates, accomplishments, and other candidate facts | `CandidateProfile` | Do not invent employers, titles, dates, skills, or achievements |
| 2. Job Description Analyzer | Job description text, read through the MCP `read_job_description_tool` | Extract responsibilities, required/preferred skills, keywords, and seniority expectations | `JobRequirements` | Keep requirements grounded in the supplied description |
| 3. Gap Analyst | Candidate profile and job requirements (`context=[extract_profile, analyze_jd]`) | Assess coverage, strengths, gaps, and honest reframing opportunities | `GapReport` | Distinguish demonstrated experience from missing or uncertain experience |
| 4. Feedback Writer | Gap report (`context=[analyze_gaps]`) | Draft tailored resume feedback, bullet suggestions, and talking points | `FeedbackDraft` | Tie factual suggestions to candidate evidence |
| 5. Interview Prep Advisor | Profile, requirements, and gaps (`context=[extract_profile, analyze_jd, analyze_gaps]`) | Prioritize topics and create a preparation plan | `InterviewPrepPlan` | Focus on role-specific gaps; do not imply unverified experience |

The agents run sequentially (`Process.sequential`, `allow_delegation: false`,
`memory: false`). Each task receives the earlier results through CrewAI's task
`context`, so there is no manager agent and no sixth task.

### Supporting workflows (not part of the crew)

- **Mock-interview workflow:** `careercrew/interview.py` asks questions, accepts text and/or voice answers, keeps a transcript, and produces per-answer and overall evaluation.
- **Preparation coach:** `careercrew/coach.py` answers follow-up questions using the resume and preparation context.
- **Post-interview coach:** `careercrew/coach.py` supports reflection using the preparation context, transcript, and evaluation results.
- **Shared guardrails and persistence:** `careercrew/guardrails.py` validates inputs and outputs; `careercrew/session_store.py` persists packages, interviews, and chats on the UI path.
