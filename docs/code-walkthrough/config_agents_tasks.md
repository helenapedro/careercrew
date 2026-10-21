# Walkthrough: `config/agents.yaml` + `config/tasks.yaml`

**File purpose:** Human-editable agent roles/goals/backstories and task descriptions/expected outputs. **No tools or MCP here** — that wiring is in `crew.py`.

---

## `agents.yaml` — five agents

Each block has: `role`, `goal`, `backstory`, `allow_delegation: false`, `verbose: true`.

| Key | Role (spoken name) | Honesty rule to say aloud |
|-----|--------------------|---------------------------|
| `profile_extractor` | Profile Extractor | Extract only what is written; leave gaps empty |
| `jd_analyzer` | Job Description Analyzer | Quote source text for each extracted item |
| `gap_analyst` | Gap Analyst | Verdicts: covered / reframeable / out_of_scope; never invent coverage |
| `feedback_writer` | Feedback Writer | Every bullet cites a profile fact; else do_not_claim |
| `interview_prep_advisor` | Interview Preparation Advisor | Focus areas cite real gaps; seniority raises the bar |

**Why `allow_delegation: false`:** Agents must not hand work to each other outside the fixed sequential task graph.

**Say this:** “These YAML blocks are the agents’ job descriptions; the Python crew attaches tools and typed outputs.”

---

## `tasks.yaml` — five tasks

Placeholders like `{resume_path}`, `{jd_text}`, and `{seniority}` are filled by `crew_inputs` at kickoff.

| Key | Agent (in crew.py) | Expected typed output | Critical instruction |
|-----|--------------------|----------------------|----------------------|
| `extract_profile` | Profile Extractor | `CandidateProfile` | File → `read_resume`; paste → use text |
| `analyze_jd` | JD Analyzer | `JobRequirements` | `read_job_description`; never treat URL as JD |
| `analyze_gaps` | Gap Analyst | `GapReport` | Score 0–100; per-requirement verdicts |
| `write_feedback` | Feedback Writer | `FeedbackDraft` | 5–8 bullets + talking points + do_not_claim |
| `build_prep_plan` | Interview Prep Advisor | `InterviewPrepPlan` | Shares ~100%; evidence = requirement text |

**Say this:** “Task text is the prompt template; expected_output is what Pydantic validation expects.”

---

## How it connects

- Loaded by `crew._load_yaml` inside `build_crew`  
- Task `context=` and `output_pydantic=` are **not** in YAML — only in [crew.md](crew.md)  
- Narrative: [CODE_PATH_ANALYZE.md](../CODE_PATH_ANALYZE.md)
