# Walkthrough: `careercrew/models.py`

**File purpose:** Pydantic contracts for every stage. Downstream code and guardrails consume **fields**, not free text — a missing fact is an empty field, not an invented sentence.

---

## Imports

| Import | Why |
|--------|-----|
| `pydantic.BaseModel`, `Field` | Validation + defaults |
| `Enum` | Review statuses/actions, seniority, interview roles |
| `datetime` / `UTC` | Timestamps on decisions, turns, chat |

`_utcnow()` — default factory for “now” in UTC.

---

## Crew task outputs

| Model | Key fields | Why the pipeline needs it |
|-------|------------|---------------------------|
| `WorkExperience` | company, title, dates, achievements | Structured resume roles |
| `CandidateProfile` | full_name, summary, skills, experience, education | Single source of truth after extract |
| `JobRequirements` | required_skills, keywords, seniority, nice_to_have | Structured JD |
| `GapVerdict` | requirement, verdict, supporting_fact | Honest per-requirement label |
| `GapReport` | coverage_score (0–100), verdicts | Match report + prep ranking |
| `RewrittenBullet` | text, cited_fact | Citation guardrail target |
| `FeedbackDraft` | rewritten_bullets, talking_points, do_not_claim | Match report rewrites |
| `ApplicationPackage` | package_id, role/company, summary, do_not_claim | Prep bundle / HITL entity |

**Say this:** “Typed outputs are the honesty backbone.”

---

## Review state machine

| Model / enum | Meaning |
|--------------|---------|
| `ReviewStatus` | DRAFT → PENDING_REVIEW → APPROVED / REJECTED |
| `ReviewAction` | APPROVE / REJECT / REVISE |
| `ReviewDecision` | package_id, decision, feedback, decided_at |
| `TraceEvent` | step, actor, detail, status, duration_ms |
| `ExecutionTrace` | list of events; `.add(...)` appends one |

**Say this:** “Trace is the audit trail of one run.”

---

## Interview preparation

| Model | Fields / notes |
|-------|----------------|
| `SeniorityBand` | early / mid / senior; `.label` → UI strings |
| `seniority_band_from_label(label)` | Match `10+` before `5-10` before `2-3` (ordering matters!) |
| `SeniorityAssessment` | band, target/detected years, confidence, rationale |
| `PrepFocus` | area, priority, suggested_share_pct, why, evidence (must cite gap) |
| `InterviewPrepPlan` | seniority + focus_areas + themes + strengths + risk_areas |

**Say this:** “Prep advice is structured so we can validate shares and evidence.”

---

## Mock interview + chat

| Model | Role |
|-------|------|
| `InterviewQuestion` | text, intent, competency, source, audio_ref |
| `InterviewTurnRole` | interviewer / candidate |
| `TranscriptTurn` | one live transcript line |
| `AnswerEvaluation` | score 0–100 + critique fields |
| `MockInterviewSession` | questions, turns, evaluations, overall_score/summary, completed |

---

## How it connects

Every agent task’s `output_pydantic=` points here; UI serializers and guardrails validate these shapes.
