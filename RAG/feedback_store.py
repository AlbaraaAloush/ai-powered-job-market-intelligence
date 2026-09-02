"""Durable feedback store; Langfuse remains the analysis destination."""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from storage import ApplicationDatabase


class FeedbackStore:
    def __init__(self, path: Path | None = None, database: ApplicationDatabase | None = None):
        self.database = database or ApplicationDatabase(sqlite_path=path)
        self._lock = threading.Lock()

    def add(self, record: dict):
        with self._lock, self.database.connect() as db:
            db.execute(
                self.database.sql("INSERT INTO rag_feedback VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"),
                (record["id"], datetime.now(timezone.utc).isoformat(), record["trace_id"],
                 record["session_id"], bool(record["helpful"]), record.get("reason", ""),
                 record.get("comment", ""), record.get("question", ""), record.get("answer", ""),
                 json.dumps(record.get("metadata", {}), ensure_ascii=False)),
            )

    @property
    def backend(self) -> str:
        return self.database.backend
