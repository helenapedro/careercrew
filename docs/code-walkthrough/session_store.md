# Walkthrough: `careercrew/session_store.py`

**File purpose:** SQLite persistence for prep bundles, HITL decisions, mock interviews, and coaching chats. Standard library only; rows survive restarts.

---

## Schema (`SCHEMA` string)

| Table | Role |
|-------|------|
| `packages` | Prep bundle JSON + inputs + trace + status + revision_count |
| `decisions` | Append-only APPROVE/REJECT/REVISE history |
| `interview_sessions` | Full session JSON + score + completed flag |
| `interview_turns` | Per-turn transcript rows (rebuilt on each save) |
| `chat_messages` | Prep/post coach turns (`channel` = prep\|post) |

---

## `SessionStore`

### `__init__(db_path)`

Create parent dirs; for `:memory:` keep one shared connection (tests); else file DB. Run `_init_schema`.

### `_connect()` context manager

Commit on success; shared vs per-call connection.

### Package APIs

| Method | What |
|--------|------|
| `save_package` | UPSERT package row (status starts DRAFT in insert; review then sets PENDING) |
| `record_decision` | INSERT decision |
| `update_status` | UPDATE status (± revision_count) |
| `get_package` | Row + parsed `ApplicationPackage` |
| `list_packages` | Package history, newest first (used by scripts/tests; no History tab) |
| `count_revisions` | Count REVISE rows |

**Say this:** “`list_packages` is the package history — that’s where `pkg-…` lives, even though the UI has no History tab.”

### Interview APIs

| Method | What |
|--------|------|
| `save_interview` | UPSERT session JSON; DELETE+reINSERT turns (no duplicates) |
| `latest_interview` | Load the most recent session model |

### Chat APIs

| Method | What |
|--------|------|
| `add_chat_message` | Append one turn (history is not read back by the UI) |

---

## How it connects

- HITL: [review.md](review.md)  
- Interview: `callbacks_interview._ask_question` / `interview_submit`  
- Coaches: `_render_*_chat`  
