# Walkthrough: `careercrew/session_store.py`

**File purpose:** SQLite persistence for prep bundles, HITL decisions, mock interviews, and coaching chats. Standard library only; survives restarts.

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
| `get_package` | Row + parsed `ScreeningPrep` |
| `get_decisions` | Oldest-first decisions |
| `list_packages` | History table (updated_at DESC) |
| `count_revisions` | Count REVISE rows |

**Say this:** “History tab is `list_packages` — that’s where `pkg-…` lives.”

### Interview APIs

| Method | What |
|--------|------|
| `save_interview` | UPSERT session JSON; DELETE+reINSERT turns (no duplicates) |
| `get_interview` / `latest_interview` | Load session model |

### Chat APIs

| Method | What |
|--------|------|
| `add_chat_message` | Append one turn |
| `get_chat_history` | Oldest-first for a channel |

---

## How it connects

- HITL: [review.md](review.md)  
- Interview: `app._ask_question` / `interview_submit`  
- Coaches: `_render_*_chat`  
