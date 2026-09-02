"""Privacy-conscious, anonymous product-usage events."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from storage import ApplicationDatabase


class UsageStore:
    """Store operational events without IPs, identities, or question text."""

    def __init__(self, database: ApplicationDatabase):
        self.database = database

    def add(
        self,
        *,
        session_id: str,
        event_type: str,
        model: str = "",
        language: str = "",
        dataset_count: int = 0,
        duration_ms: float | None = None,
        success: bool = True,
        metadata: dict | None = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        with self.database.connect() as db:
            db.execute(
                self.database.sql(
                    "INSERT INTO usage_events "
                    "(id, occurred_at, session_id, event_type, model, language, "
                    "dataset_count, duration_ms, success, metadata_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                ),
                (
                    event_id,
                    datetime.now(timezone.utc).isoformat(),
                    session_id,
                    event_type,
                    model,
                    language,
                    max(0, int(dataset_count)),
                    duration_ms,
                    bool(success),
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
        return event_id

    @property
    def backend(self) -> str:
        return self.database.backend
