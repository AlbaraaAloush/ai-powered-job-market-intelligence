"""Schema gate and reproducible per-file data-quality report for ingestion."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from data_loader import COLUMN_ALIASES, _build_rename_map, _load_file, parse_file_info

REQUIRED_FIELDS = ("job_id", "job_title")


def inspect_file(path: Path) -> dict:
    raw = _load_file(path)
    frame = raw.rename(columns=_build_rename_map(list(raw.columns)))
    missing = [c for c in REQUIRED_FIELDS if c not in frame.columns]
    duplicate_ids = int(frame["job_id"].duplicated().sum()) if "job_id" in frame else 0
    null_rates = {
        c: round(float(frame[c].isna().mean()), 4)
        for c in ("job_id", "job_title", "company", "description", "salary") if c in frame
    }
    info = parse_file_info(path)
    return {
        "file": path.name, "source": info["source"], "country": info["country"],
        "timeline": info["timeline"], "rows": len(frame), "columns": len(frame.columns),
        "schema_valid": not missing, "missing_required_fields": missing,
        "duplicate_job_ids": duplicate_ids, "null_rates": null_rates,
        "warnings": (["unknown_country"] if info["country"] == "Unknown" else []) +
                    (["duplicate_job_ids"] if duplicate_ids else []),
    }


def build_quality_report(files: list[str], output: Path, *, fail_on_schema: bool = True) -> dict:
    reports = [inspect_file(Path(file)) for file in files]
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "job-ingestion-v1", "files": reports,
        "summary": {"files": len(reports), "rows": sum(r["rows"] for r in reports),
                    "invalid_files": sum(not r["schema_valid"] for r in reports)},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    invalid = [r["file"] for r in reports if not r["schema_valid"]]
    if invalid and fail_on_schema:
        raise ValueError(f"Ingestion schema validation failed: {', '.join(invalid)}")
    return result
