"""Build the browser-ready dashboard snapshot from the source workbooks.

Run this only when the Excel/CSV snapshots change.  The generated files are
committed with the frontend and served as static Vercel assets; production
visitors never parse Excel or wait for the RAG backend.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from config import DATA_DIR
from dashboard_service import (
    DashboardDataService,
    SALARY_BINS,
    SALARY_LABELS,
    _city_series,
    _company_size_series,
    _parse_salary_mid,
    _split_skills,
)
from data_loader import load_all


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "frontend" / "public" / "data" / "dashboard"
DETAIL_DIR = OUTPUT_DIR / "postings"
SCHEMA_VERSION = 1
ARABIC_TOKEN = re.compile(r"[\u0600-\u06ff]{3,}")


def _value(value):
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def _text(value, limit: int | None = None) -> str | None:
    value = _value(value)
    if value is None:
        return None
    result = str(value).strip()
    if not result:
        return None
    return result[:limit] if limit else result


def _salary_bracket(mid: float | None) -> str | None:
    if mid is None:
        return None
    for index, label in enumerate(SALARY_LABELS):
        if SALARY_BINS[index] <= mid < SALARY_BINS[index + 1]:
            return label
    return None


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"{cleaned or 'dataset'}-{digest}.json"


def _dump_metadata(df: pd.DataFrame) -> list[dict]:
    columns = ["_dump_id", "_country", "_timeline", "_dump_label"]
    if "_source" in df.columns:
        columns.append("_source")
    grouped = df.groupby(columns, dropna=False).size().reset_index(name="count")
    rows = grouped.to_dict("records")
    rows.sort(key=lambda row: (str(row.get("_source", "")), str(row["_country"]), str(row["_timeline"])))
    return [{key: _value(value) for key, value in row.items()} for row in rows]


def _source_version() -> tuple[str, list[dict]]:
    files = sorted(
        path for path in (*DATA_DIR.glob("*.xlsx"), *DATA_DIR.glob("*.csv"))
        if not path.name.startswith("~$")
    )
    sources = [
        {"name": path.name, "bytes": path.stat().st_size, "modified_ns": path.stat().st_mtime_ns}
        for path in files
    ]
    encoded = json.dumps(sources, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16], sources


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAIL_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading and normalizing source workbooks (one-time build step)...")
    df, timelines = load_all(DATA_DIR, compact=False)
    df = df.reset_index(drop=True)

    remote = DashboardDataService._signal_mask(df, "_remote_signal")
    nationalization = DashboardDataService._signal_mask(df, "_national_signal")
    bilingual = (
        df["_ar_content"].notna()
        if "_ar_content" in df.columns
        else df.get("_has_ar_content", pd.Series(False, index=df.index)).fillna(False).astype(bool)
    )
    cities = _city_series(df)
    company_sizes = _company_size_series(df)

    # Keep only globally relevant Arabic terms in the browser snapshot. Raw
    # Arabic portal pages are intentionally excluded from deployment data.
    term_sets: list[set[str]] = []
    term_counter: Counter[str] = Counter()
    ar_values = df.get("_ar_content", pd.Series(None, index=df.index))
    for value in ar_values:
        terms = set(ARABIC_TOKEN.findall(str(value))) if _text(value) else set()
        term_sets.append(terms)
        term_counter.update(terms)
    retained_terms = {term for term, _ in term_counter.most_common(100)}

    analytics: list[dict] = []
    details_by_dump: dict[str, list[dict]] = defaultdict(list)

    for index, row in df.iterrows():
        dump_id = _text(row.get("_dump_id")) or "unknown"
        job_id = _text(row.get("job_id"))
        key = f"{dump_id}:{job_id or index}"
        salary_mid = _parse_salary_mid(row.get("salary"))
        skills = _split_skills(row.get("skills"))

        analytics.append({
            "key": key,
            "dump": dump_id,
            "country": _text(row.get("_country")),
            "timeline": _text(row.get("_timeline")),
            "title": _text(row.get("job_title")),
            "company": _text(row.get("company")),
            "sector": _text(row.get("_sector_norm")) or _text(row.get("category")),
            "category": _text(row.get("category")),
            "location": _text(row.get("location")),
            "city": _text(cities.iloc[index]),
            "salary": _text(row.get("salary")),
            "salaryMid": round(salary_mid, 2) if salary_mid is not None else None,
            "salaryBracket": _salary_bracket(salary_mid),
            "employmentType": _text(row.get("_employment_norm")) or _text(row.get("employment_type")),
            "careerLevel": _text(row.get("_career_norm")) or _text(row.get("career_level")),
            "experience": _text(row.get("experience")),
            "companySize": _text(row.get("company_size")),
            "companySizeBucket": _text(company_sizes.iloc[index]),
            "skills": skills,
            "education": _text(row.get("education")),
            "gender": _text(row.get("gender")),
            "language": _text(row.get("language")),
            "remote": bool(remote.iloc[index]),
            "nationalization": bool(nationalization.iloc[index]),
            "bilingual": bool(bilingual.iloc[index]),
            "arabicTerms": sorted(term_sets[index] & retained_terms),
        })

        details_by_dump[dump_id].append({
            "key": key,
            "job_id": _value(row.get("job_id")),
            "description": _text(row.get("description"), 1200),
            "qualifications": _text(row.get("qualifications"), 800),
            "url": _text(row.get("url")),
            "post_date": _text(row.get("post_date")),
        })

    data_version, sources = _source_version()
    analytics_name = f"analytics-{data_version}.json"
    analytics_path = OUTPUT_DIR / analytics_name
    analytics_path.write_text(
        json.dumps(analytics, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    posting_files: dict[str, str] = {}
    for dump_id, records in sorted(details_by_dump.items()):
        filename = _safe_filename(dump_id)
        (DETAIL_DIR / filename).write_text(
            json.dumps(records, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        posting_files[dump_id] = f"postings/{filename}"

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "data_version": data_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(analytics),
        "analytics_file": analytics_name,
        "posting_files": posting_files,
        "datasets": {
            "dumps": _dump_metadata(df),
            "timelines": timelines,
            "sources": sorted(df["_source"].dropna().unique().tolist()) if "_source" in df.columns else [],
        },
        "source_files": sources,
    }
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    analytics_mb = analytics_path.stat().st_size / 1024 / 1024
    details_mb = sum(path.stat().st_size for path in DETAIL_DIR.glob("*.json")) / 1024 / 1024
    print(f"Static dashboard ready: {len(analytics):,} records")
    print(f"  manifest:  {OUTPUT_DIR / 'manifest.json'}")
    print(f"  analytics: {analytics_mb:.2f} MB")
    print(f"  details:   {details_mb:.2f} MB across {len(posting_files)} files")


if __name__ == "__main__":
    main()
