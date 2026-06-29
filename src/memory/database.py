"""
Database — SQLite Persistence for Audit Logging and State

Provides persistent storage for:
- Execution event logs (what happened and when)
- Task status tracking
- Historical workflow records

Uses SQLite for zero-configuration, file-based persistence.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from src.config import Config

logger = logging.getLogger(__name__)


class Database:
    """
    SQLite-backed persistence engine for logging and state tracking.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or Config.DATABASE_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info(f"Database initialized: {self._db_path}")

    def _create_tables(self) -> None:
        """Create tables if they don't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                data TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workflows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                goal TEXT NOT NULL,
                plan TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                result TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
            CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status);
        """)
        self._conn.commit()

    def log_event(self, event_type: str, data: dict) -> int:
        """
        Log an event to the database.

        Args:
            event_type: Category of event (e.g., "plan_start", "task_complete").
            data: Arbitrary event data.

        Returns:
            The row ID of the inserted event.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            "INSERT INTO events (timestamp, event_type, data) VALUES (?, ?, ?)",
            (timestamp, event_type, json.dumps(data)),
        )
        self._conn.commit()
        logger.debug(f"Logged event: {event_type}")
        return cursor.lastrowid

    def get_events(self, event_type: str | None = None, limit: int = 100) -> list[dict]:
        """
        Retrieve logged events, optionally filtered by type.

        Returns:
            List of event dicts.
        """
        if event_type:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE event_type = ? ORDER BY id DESC LIMIT ?",
                (event_type, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "event_type": row["event_type"],
                "data": json.loads(row["data"]),
            }
            for row in rows
        ]

    def save_workflow(self, goal: str, plan: dict) -> int:
        """Save a workflow record and return its ID."""
        timestamp = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            "INSERT INTO workflows (timestamp, goal, plan, status) VALUES (?, ?, ?, ?)",
            (timestamp, goal, json.dumps(plan), "running"),
        )
        self._conn.commit()
        return cursor.lastrowid

    def update_workflow_status(self, workflow_id: int, status: str, result: dict | None = None) -> None:
        """Update the status and result of a workflow."""
        self._conn.execute(
            "UPDATE workflows SET status = ?, result = ? WHERE id = ?",
            (status, json.dumps(result) if result else None, workflow_id),
        )
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
        logger.info("Database connection closed.")
