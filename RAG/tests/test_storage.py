import os
import time
import uuid

from feedback_store import FeedbackStore
from session import MAX_MESSAGES, PersistentSessionStore
from storage import ApplicationDatabase
from usage_store import UsageStore


def _database(tmp_path):
    url = os.getenv("DATABASE_URL", "").strip()
    return ApplicationDatabase(database_url=url, sqlite_path=tmp_path / "application.sqlite3")


def test_database_migration_and_health(tmp_path):
    database = _database(tmp_path)
    assert database.ping()
    assert database.backend in {"sqlite", "postgresql"}


def test_feedback_is_durable_and_trace_linked(tmp_path):
    database = _database(tmp_path)
    store = FeedbackStore(database=database)
    record_id, trace_id = str(uuid.uuid4()), uuid.uuid4().hex
    store.add({
        "id": record_id, "trace_id": trace_id, "session_id": str(uuid.uuid4()),
        "helpful": False, "reason": "inaccurate", "comment": "wrong count",
        "question": "How many?", "answer": "Unknown", "metadata": {"test": True},
    })
    with database.connect() as db:
        row = db.execute(database.sql("SELECT helpful, reason FROM rag_feedback WHERE id = ?"), (record_id,)).fetchone()
    assert bool(row[0]) is False
    assert row[1] == "inaccurate"


def test_persistent_sessions_survive_store_recreation_and_trim(tmp_path):
    database = _database(tmp_path)
    first = PersistentSessionStore(database)
    sid = first.create()
    for index in range(MAX_MESSAGES + 3):
        first.append(sid, "user", f"message-{index}")
    second = PersistentSessionStore(database)
    history = second.get_history(sid)
    assert len(history) == MAX_MESSAGES
    assert history[-1]["content"] == f"message-{MAX_MESSAGES + 2}"
    second.clear(sid)
    assert first.get_history(sid) == []


def test_persistent_session_cleanup(tmp_path):
    database = _database(tmp_path)
    store = PersistentSessionStore(database)
    sid = store.create()
    with database.connect() as db:
        db.execute(database.sql("UPDATE chat_sessions SET last_seen = ? WHERE id = ?"), (0, sid))
    assert store.cleanup() >= 1


def test_anonymous_usage_event_is_durable(tmp_path):
    database = _database(tmp_path)
    store = UsageStore(database)
    sid = str(uuid.uuid4())
    event_id = store.add(
        session_id=sid,
        event_type="chat_completed",
        model="fanar",
        language="en",
        dataset_count=6,
        duration_ms=1250.5,
        metadata={"mode": "analytics"},
    )
    with database.connect() as db:
        row = db.execute(
            database.sql(
                "SELECT session_id, event_type, duration_ms, metadata_json "
                "FROM usage_events WHERE id = ?"
            ),
            (event_id,),
        ).fetchone()
    assert row[0] == sid
    assert row[1] == "chat_completed"
    assert float(row[2]) == 1250.5
    assert "analytics" in row[3]
