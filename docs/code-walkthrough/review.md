# Walkthrough: `careercrew/review.py`

**File purpose:** Human-in-the-loop state machine for the prep bundle. No silent auto-approve.

**Flow:** [CODE_PATH_HITL.md](../CODE_PATH_HITL.md)

---

## `ReviewError`

Raised for illegal transitions or revision limit exceeded.

## `_ALLOWED` map

| From | To |
|------|-----|
| DRAFT | PENDING_REVIEW |
| PENDING_REVIEW | APPROVED, REJECTED, DRAFT (revise) |
| APPROVED / REJECTED | (none — terminal) |

### `_check_transition(current, target)`

Raise if target not in allowed set.

---

## `ReviewOutcome`

status, message, revision_count, needs_revision flag.

---

## `PackageReviewService`

### `__init__(store, max_revisions=None)`

Defaults `max_revisions` from settings (`CAREERCREW_MAX_REVISIONS`, default 2).

### `submit_for_review(inputs, package, trace, status=DRAFT, revision_count=0)`

**What:** Check DRAFT→PENDING_REVIEW; `save_package`; `update_status(PENDING_REVIEW)`.  
**When:** End of Analyze.  
**Say this:** “Analyze always parks the bundle for human review.”

### `apply_decision(package, decision, current_status, revision_count)`

**What:**

- Must be PENDING_REVIEW; decision.package_id must match  
- APPROVE / REJECT → `_persist` + outcome  
- REVISE → require non-empty feedback; increment revision_count; refuse if > max; status → DRAFT; `needs_revision=True`  

**Say this:** “Revise without notes is illegal; max two revision cycles by default.”

### `_persist` / `can_revise`

Write decision row + status; helper for UI enablement.

---

## How it connects

`app.approve` / `reject` / `request_revision` → this service → [session_store.md](session_store.md).
