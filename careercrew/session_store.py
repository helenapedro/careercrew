"""Save prep bundles, interviews, and coach chats in SQLite.

What it does: stores one row per bundle so a refresh does not lose the review.
Who calls it: the review service and the interview and coach callbacks.
What it returns: the saved row, or None when the id is unknown.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from careercrew.models import (
    ApplicationPackage,
    ReviewDecision,
    ReviewStatus,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS packages (
    package_id     TEXT PRIMARY KEY,
    role_title     TEXT NOT NULL DEFAULT '',
    company        TEXT NOT NULL DEFAULT '',
    inputs_json    TEXT NOT NULL,
    package_json   TEXT NOT NULL,
    trace_json     TEXT,
    status         TEXT NOT NULL,
    revision_count INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id  TEXT NOT NULL,
    decision    TEXT NOT NULL,
    feedback    TEXT NOT NULL DEFAULT '',
    decided_at  TEXT NOT NULL,
    FOREIGN KEY (package_id) REFERENCES packages(package_id)
);

CREATE TABLE IF NOT EXISTS interview_sessions (
    session_id      TEXT PRIMARY KEY,
    package_id      TEXT,
    role_title      TEXT NOT NULL DEFAULT '',
    session_json    TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interview_turns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    question_index  INTEGER NOT NULL DEFAULT 0,
    role            TEXT NOT NULL,
    text            TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    channel     TEXT NOT NULL DEFAULT 'prep',
    role        TEXT NOT NULL DEFAULT 'user',
    content     TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SessionStore:
    """SQLite-backed store for packages and review decisions."""

    def __init__(self, db_path: str | Path = "careercrew.db") -> None:
        self.db_path = str(db_path)
        # For an in-memory database every new connection would be a fresh, empty
        # database, so keep a single shared connection instead.
        self._shared: sqlite3.Connection | None = None
        if self.db_path == ":memory:":
            self._shared = sqlite3.connect(":memory:")
            self._shared.row_factory = sqlite3.Row
        else:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # -- connection helpers ----------------------------------------------------
    @contextmanager
    def _connect(self):
        if self._shared is not None:
            try:
                yield self._shared
                self._shared.commit()
            finally:
                pass
            return
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    # -- writes ----------------------------------------------------------------
    def save_package(
        self,
        inputs: dict,
        package: ApplicationPackage,
        trace=None,
        revision_count: int = 0,
    ) -> None:
        """Insert or update the stored package row."""
        import json

        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO packages
                    (package_id, role_title, company, inputs_json, package_json,
                     trace_json, status, revision_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(package_id) DO UPDATE SET
                    role_title = excluded.role_title,
                    company = excluded.company,
                    inputs_json = excluded.inputs_json,
                    package_json = excluded.package_json,
                    trace_json = excluded.trace_json,
                    status = excluded.status,
                    revision_count = excluded.revision_count,
                    updated_at = excluded.updated_at
                """,
                (
                    package.package_id,
                    package.role_title,
                    package.company,
                    json.dumps(inputs, default=str),
                    package.model_dump_json(),
                    trace.model_dump_json() if trace else None,
                    ReviewStatus.DRAFT.value,
                    revision_count,
                    now,
                    now,
                ),
            )

    def record_decision(self, decision: ReviewDecision) -> None:
        """Persist a review decision (append-only history)."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO decisions (package_id, decision, feedback, decided_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    decision.package_id,
                    decision.decision.value,
                    decision.reviewer_feedback,
                    decision.decided_at.isoformat(),
                ),
            )

    def update_status(
        self, package_id: str, status: ReviewStatus, revision_count: int | None = None
    ) -> None:
        """Update the lifecycle status (and optionally revision count)."""
        with self._connect() as conn:
            if revision_count is None:
                conn.execute(
                    "UPDATE packages SET status = ?, updated_at = ? WHERE package_id = ?",
                    (status.value, _now(), package_id),
                )
            else:
                conn.execute(
                    "UPDATE packages SET status = ?, revision_count = ?, updated_at = ? "
                    "WHERE package_id = ?",
                    (status.value, revision_count, _now(), package_id),
                )

    # -- reads -----------------------------------------------------------------
    def get_package(self, package_id: str) -> dict | None:
        """Return a package row (with parsed package) or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM packages WHERE package_id = ?", (package_id,)
            ).fetchone()
        if row is None:
            return None
        import json

        data = dict(row)
        data["package"] = ApplicationPackage.model_validate_json(data["package_json"])
        try:
            data["inputs"] = json.loads(data.get("inputs_json") or "{}")
        except (TypeError, ValueError):
            data["inputs"] = {}
        return data

    # -- interview sessions ----------------------------------------------------
    def save_interview(self, session, package_id: str | None = None) -> None:
        """Insert or update a mock interview session (with its transcript turns)."""
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO interview_sessions
                    (session_id, package_id, role_title, session_json,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    session_json = excluded.session_json,
                    updated_at = excluded.updated_at
                """,
                (
                    session.session_id,
                    package_id,
                    session.role_title,
                    session.model_dump_json(),
                    now,
                    now,
                ),
            )
            # Rebuild the turn rows so re-saving never duplicates them.
            conn.execute("DELETE FROM interview_turns WHERE session_id = ?", (session.session_id,))
            for turn in session.turns:
                conn.execute(
                    "INSERT INTO interview_turns (session_id, question_index, role, text, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        session.session_id,
                        turn.question_index,
                        turn.role.value,
                        turn.text,
                        turn.created_at.isoformat(),
                    ),
                )

    def latest_interview(self):
        """Return the most recently updated mock interview session, or None."""
        from careercrew.models import MockInterviewSession

        with self._connect() as conn:
            row = conn.execute(
                "SELECT session_json FROM interview_sessions ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return MockInterviewSession.model_validate_json(row["session_json"])

    # -- coaching chats --------------------------------------------------------
    def add_chat_message(self, session_id: str, channel: str, role: str, content: str) -> None:
        """Append one chat turn for a channel ('prep' or 'post')."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO chat_messages (session_id, channel, role, content, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, channel, role, content, _now()),
            )
