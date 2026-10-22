# Code path: Human-in-the-loop (approve / revise / reject)

After Analyze, the prep bundle is stored as **`PENDING_REVIEW`**. The dock
**Your decision** lets a human approve, request changes, or reject. Nothing is
submitted to an employer.

**Upstream:** [CODE_PATH_ANALYZE.md](CODE_PATH_ANALYZE.md) step 13.

---

## 1. State machine

Implemented in [`careercrew/review.py`](../careercrew/review.py).

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> PENDING_REVIEW : submit_for_review
    PENDING_REVIEW --> APPROVED : approve
    PENDING_REVIEW --> REJECTED : reject
    PENDING_REVIEW --> DRAFT : request_revision
    APPROVED --> [*]
    REJECTED --> [*]
```

| From | Allowed to | Trigger |
|------|------------|---------|
| `DRAFT` | `PENDING_REVIEW` | `PackageReviewService.submit_for_review` (end of Analyze) |
| `PENDING_REVIEW` | `APPROVED` | UI **Approve prep bundle** |
| `PENDING_REVIEW` | `REJECTED` | UI **Reject** |
| `PENDING_REVIEW` | `DRAFT` | UI **Request changes** (requires notes; revision count++) |
| `APPROVED` / `REJECTED` | — | Terminal |

Revision limit: `CAREERCREW_MAX_REVISIONS` (default **2**) via `Settings.max_revisions`. Exceeding → `ReviewError`.

Enums: `ReviewStatus`, `ReviewAction` in [`models.py`](../careercrew/models.py).

---

## 2. Submit for review (automatic after Analyze)

| Step | Code | Persistence |
|------|------|-------------|
| 1 | `callbacks_analyze.analyze` calls `_REVIEW.submit_for_review(inputs, result.package, result.trace)` | |
| 2 | `save_package(inputs, package, trace, revision_count)` | **INSERT/UPSERT** SQLite `packages` |
| 3 | `update_status(..., PENDING_REVIEW)` | Status column |
| 4 | Enable Approve / Reject / Revise buttons | Gradio `interactive=True` |

**SQLite `packages` columns written:** `package_id`, `role_title`, `company`, `inputs_json`, `package_json`, `trace_json`, `status`, `revision_count`, timestamps.

Store: [`careercrew/session_store.py`](../careercrew/session_store.py).

---

## 3. UI handlers

| Button | Handler in `callbacks_analyze.py` | Service call |
|--------|---------------------|--------------|
| Approve prep bundle | `approve(state, feedback)` | `apply_decision(..., APPROVE)` |
| Request changes | `request_revision(state, feedback)` | Candidate adds missing experience (e.g. React years). Notes are **merged into the resume**, then Analyze re-runs so gaps / prep / rewrites update. |
| Reject | `reject(state, feedback)` | `apply_decision(..., REJECT)` |

Shared pattern:

1. `_load_package(state)` → `ApplicationPackage`  
2. `_current_status(package)` → read SQLite status + revision_count  
3. `ReviewDecision(package_id, decision, reviewer_feedback)`  
4. `_REVIEW.apply_decision(...)`  
5. Refresh the decision dock (`_review_guide_html`) + status line  

On success, approve message includes the prep-bundle id (`pkg-…`).

---

## 4. Decisions table

Each approve/reject/revise also **INSERT**s into SQLite `decisions`:

| Column | Meaning |
|--------|---------|
| `package_id` | FK to packages |
| `decision` | `approve` / `reject` / `revise` |
| `feedback` | Notes from the textbox |
| `decided_at` | UTC ISO timestamp |

---

## 5. Where the package id lives

There is no History tab in the current UI. The prep bundle id (`pkg-…`) appears
in the Analyze status line, in the decision dock, and in the approve / reject
messages. The same id is the primary key of the SQLite `packages` row, so
`_STORE.get_package("pkg-…")` returns the stored package, its inputs, and its
trace.

---

## 6. Talking points

- HITL is real persistence, not a fake button  
- **Approval gates downstream use**: the mock interview and both coaching chats
  check `_is_approved()` (`careercrew/callbacks_interview.py`) and refuse to run
  while the bundle is `PENDING_REVIEW`, telling the user to press **Approve prep
  bundle**. The gate reads the persisted `packages.status`, so it survives a
  session reload.
- Approve does **not** call any employer API  
- Revise without notes is rejected by the service  
- **Request changes** means “I have experience that wasn’t on my resume” → merge into resume → re-analyze → refresh Match / Prep  
- After terminal APPROVED/REJECTED, further decisions fail until a new Analyze  
