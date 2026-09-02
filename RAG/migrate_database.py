"""Create or upgrade application tables using DATABASE_URL (or local SQLite)."""
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from storage import ApplicationDatabase

load_dotenv()

if __name__ == "__main__":
    url = os.getenv("DATABASE_URL", "").strip()
    database = ApplicationDatabase(
        database_url=url,
        sqlite_path=Path(__file__).parent / "chroma_db" / "application.sqlite3",
    )
    legacy = Path(__file__).parent / "chroma_db" / "feedback.sqlite3"
    migrated = 0
    if legacy.exists():
        with sqlite3.connect(legacy) as source, database.connect() as target:
            try:
                rows = source.execute(
                    "SELECT id, created_at, trace_id, session_id, helpful, reason, comment, question, answer, metadata_json FROM rag_feedback"
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
            for row in rows:
                row = (*row[:4], bool(row[4]), *row[5:])
                target.execute(database.sql(
                    "INSERT INTO rag_feedback VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING"
                ), row)
                migrated += 1
    if not database.ping():
        raise SystemExit("Database migration completed but health check failed")
    print(f"Application database ready ({database.backend}); legacy feedback considered: {migrated}.")
