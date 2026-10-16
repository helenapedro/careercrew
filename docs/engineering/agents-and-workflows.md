## 7. Agent Roles and Tasks

The roles below represent the proposed analysis workflow. Their exact prompts, contracts, ordering, and execution behavior must be confirmed against the current code.

| Agent / role | Inputs | Responsibilities | Expected output | Guardrails |
|---|---|---|---|---|
| 1. Profile Extractor | Resume or professional-experience source | Extract skills, roles, dates, accomplishments, and other candidate facts | `CandidateProfile` or equivalent structured profile | Do not invent employers, titles, dates, skills, or achievements |
| 2. Job Description Analyzer | Job description | Extract responsibilities, required/preferred skills, keywords, and seniority expectations | `JobRequirements` or equivalent structure | Keep requirements grounded in the supplied description |
| 3. Gap Analyst | Candidate profile and job requirements | Assess coverage, strengths, gaps, and honest reframing opportunities | `GapReport` or equivalent | Distinguish demonstrated experience from missing or uncertain experience |
| 4. Feedback Writer | Candidate profile, job description, gap report | Draft tailored resume feedback, bullet suggestions, and talking points | `FeedbackDraft` or equivalent | Tie factual suggestions to candidate evidence |
| 5. Interview Prep Advisor | Candidate profile, role requirements, gaps, target experience level | Prioritize topics and create a preparation plan | `InterviewPrepPlan` or equivalent | Focus on role-specific gaps; do not imply unverified experience |
| 6. Screening Answer Prep Writer | Screening questions and verified answer bank or candidate evidence | Draft supported screening answers and flag unknowns | `ScreeningPrep` or equivalent | Never invent personal facts or submit answers |

### Supporting workflows (not necessarily separate CrewAI agents)

- **Mock-interview workflow:** asks questions, accepts text and/or voice answers, maintains a transcript, and produces per-answer feedback or an overall evaluation where implemented.
- **Preparation coach:** answers follow-up questions using relevant resume and preparation context where implemented.
- **Post-interview coach:** supports reflection using available preparation context, transcript, and evaluation results where implemented.
- **Shared guardrails and persistence:** may be used across workflows; exact behavior must be verified in code.
