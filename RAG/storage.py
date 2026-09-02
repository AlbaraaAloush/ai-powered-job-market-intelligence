"""Application persistence for managed PostgreSQL and local SQLite."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class ApplicationDatabase:
    def __init__(self, database_url: str = "", sqlite_path: Path | None = None):
        self.database_url = database_url.strip()
        self.sqlite_path = sqlite_path
        self.backend = "postgresql" if self.database_url else "sqlite"
        if self.backend == "sqlite":
            if sqlite_path is None:
                raise ValueError("sqlite_path is required when DATABASE_URL is unset")
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connect(self):
        if self.backend == "postgresql":
            import psycopg
            with psycopg.connect(self.database_url, connect_timeout=10) as connection:
                yield connection
        else:
            with sqlite3.connect(self.sqlite_path, timeout=10) as connection:
                connection.execute("PRAGMA foreign_keys = ON")
                yield connection

    def sql(self, statement: str) -> str:
        return statement.replace("?", "%s") if self.backend == "postgresql" else statement

    def migrate(self) -> None:
        message_id = "BIGSERIAL PRIMARY KEY" if self.backend == "postgresql" else "INTEGER PRIMARY KEY AUTOINCREMENT"
        statements = [
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS rag_feedback (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, trace_id TEXT NOT NULL,
                session_id TEXT NOT NULL, helpful BOOLEAN NOT NULL, reason TEXT,
                comment TEXT, question TEXT, answer TEXT, metadata_json TEXT NOT NULL
            )""",
            """CREATE INDEX IF NOT EXISTS idx_rag_feedback_trace
               ON rag_feedback(trace_id)""",
            """CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY, last_seen DOUBLE PRECISION NOT NULL
            )""",
            f"""CREATE TABLE IF NOT EXISTS chat_messages (
                id {message_id}, session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                role TEXT NOT NULL, content TEXT NOT NULL, created_at DOUBLE PRECISION NOT NULL
            )""",
            """CREATE INDEX IF NOT EXISTS idx_chat_messages_session
               ON chat_messages(session_id, id)""",
            """CREATE TABLE IF NOT EXISTS usage_events (
                id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL,
                session_id TEXT NOT NULL, event_type TEXT NOT NULL,
                model TEXT, language TEXT, dataset_count INTEGER NOT NULL DEFAULT 0,
                duration_ms DOUBLE PRECISION, success BOOLEAN NOT NULL,
                metadata_json TEXT NOT NULL
            )""",
            """CREATE INDEX IF NOT EXISTS idx_usage_events_occurred
               ON usage_events(occurred_at)""",
            """CREATE INDEX IF NOT EXISTS idx_usage_events_session
               ON usage_events(session_id)""",
            """CREATE INDEX IF NOT EXISTS idx_usage_events_type
               ON usage_events(event_type)""",
        ]
        with self.connect() as db:
            for statement in statements:
                db.execute(statement)
            db.execute(
                self.sql("INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?) ON CONFLICT(version) DO NOTHING"),
                (1, __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()),
            )
            db.execute(
                self.sql("INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?) ON CONFLICT(version) DO NOTHING"),
                (2, __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()),
            )

    def ping(self) -> bool:
        try:
            with self.connect() as db:
                db.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False
