from __future__ import annotations

import pandas as pd

from data_loader import build_runtime_snapshot, load_all


def test_runtime_snapshot_is_reused_and_invalidated(tmp_path):
    source = tmp_path / "bayt_jobs_Qatar_12_May_2026.csv"
    pd.DataFrame([
        {"job_id": 1, "job_title": "Data Analyst", "company": "Example", "skills": "SQL, Python"},
    ]).to_csv(source, index=False)

    parquet, manifest, count = build_runtime_snapshot(tmp_path)
    assert parquet.exists() and manifest.exists() and count == 1

    cached, timelines = load_all(tmp_path, compact=True)
    assert len(cached) == 1
    assert timelines == ["May 2026"]
    assert str(cached.iloc[0]["job_id"]) == "1"

    # A changed source fingerprint must reject the stale snapshot and parse
    # the source again instead of serving old data.
    pd.DataFrame([
        {"job_id": 1, "job_title": "Data Analyst", "company": "Example"},
        {"job_id": 2, "job_title": "Data Scientist", "company": "Example"},
    ]).to_csv(source, index=False)
    refreshed, _ = load_all(tmp_path, compact=True)
    assert len(refreshed) == 2
