"""
data_loader.py
--------------
Scans data/ for EN and AR Excel/CSV files, parses country + timeline from
the filename, normalises column names, applies substring-based normalization
for career level and employment type (catches ALL variants), merges Arabic
signals where an AR counterpart exists, and returns a combined DataFrame.

Filename convention (professor's format):
  EN:  bayt_jobs_{Country}_{Day}_{Month}_{Year}.xlsx
  AR:  bayt_jobs_{Country}_AR_{Day}_{Month}_{Year}.xlsx

Examples:
  bayt_jobs_Qatar_22_Nov_2025.xlsx       → country=Qatar, timeline=Nov 2025
  bayt_jobs_Saudi_Arabia_AR_12_May_2026.xlsx → country=Saudi Arabia, AR signals
"""

import hashlib
import json
import re
import pandas as pd
from pathlib import Path
from config import DATA_DIR, COLUMN_ALIASES

RUNTIME_PARQUET = "runtime_compact.parquet"
RUNTIME_MANIFEST = "runtime_compact.json"
RUNTIME_SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Month helpers
# ---------------------------------------------------------------------------

_MONTH_MAP: dict[str, str] = {
    "january": "Jan",  "jan": "Jan",
    "february": "Feb", "feb": "Feb",
    "march": "Mar",    "mar": "Mar",
    "april": "Apr",    "apr": "Apr",
    "may": "May",
    "june": "Jun",     "jun": "Jun",
    "july": "Jul",     "jul": "Jul",
    "august": "Aug",   "aug": "Aug",
    "september": "Sep","sep": "Sep",
    "october": "Oct",  "oct": "Oct",
    "november": "Nov", "nov": "Nov",
    "december": "Dec", "dec": "Dec",
}

_MONTH_ORDER = {v: i for i, v in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
)}


# ---------------------------------------------------------------------------
# Substring-based normalization  (catches ALL variants — fixes wrong answers)
# ---------------------------------------------------------------------------

def norm_employment(val) -> str | None:
    """
    Map any employment-type string to a canonical label using substring match.
    Handles: Full-Time / full time / fulltime / Full Time / FULL-TIME / etc.
    """
    if pd.isna(val) or not str(val).strip():
        return None
    s = str(val).strip().lower().replace("-", " ").replace("_", " ")
    if "full" in s and "time" in s:        return "Full-Time"
    if "part" in s and "time" in s:        return "Part-Time"
    if "contract" in s:                    return "Contract"
    if "freelance" in s or "free lance" in s: return "Freelance"
    if "intern" in s:                      return "Internship"
    if "temp" in s:                        return "Temporary"
    return str(val).strip()                # keep original if unrecognised


def norm_career(val) -> str | None:
    """
    Map any career-level string to a canonical label using substring match.
    Uses the same logic as the professor's norm_career() to ensure our numbers
    match his dashboard exactly.
    """
    if pd.isna(val) or not str(val).strip():
        return None
    s = str(val).strip().lower()

    # Order matters: most specific first
    if any(x in s for x in ["executive", "c-level", "chief", "إدارة عليا تنفيذية"]):
        return "Executive"
    if "director" in s:
        return "Director"
    # Senior management → Executive (more senior than regular Manager)
    if "senior management" in s or "senior mgmt" in s or "senior managerial" in s:
        return "Executive"
    # Management / manager / supervisory → Manager
    if any(x in s for x in ["manager", "managerial", "management", "إدارة"]):
        return "Manager"
    if "senior" in s or "sr." in s:
        return "Senior"
    if any(x in s for x in ["supervisor", "supervisory"]):
        return "Manager"
    # Mid-level — catches consultant, متوسط الخبرة, intermediate, professional, etc.
    if any(x in s for x in ["mid", "intermediate", "consultant", "professional",
                              "experienced hire", "متوسط", "associate"]):
        return "Mid-Level"
    # Entry level
    if any(x in s for x in ["entry", "junior", "graduate", "مبتدئ",
                              "intern", "trainee", "student", "undergraduate",
                              "fresh", "early career"]):
        return "Entry-Level"
    return str(val).strip()   # keep original if unrecognised


SALARY_BUCKET_BINS: list[float] = [0, 500, 1000, 1500, 2000, 3000, 5000, 7500, 10000, 15000, float("inf")]
SALARY_BUCKET_LABELS: list[str] = [
    "<$500", "$500-1K", "$1K-1.5K", "$1.5K-2K", "$2K-3K",
    "$3K-5K", "$5K-7.5K", "$7.5K-10K", "$10K-15K", "$15K+",
]


def parse_salary_mid(val) -> float | None:
    """Parse a free-text salary range string into a monthly USD midpoint."""
    if not val or str(val).strip() == "":
        return None
    s = str(val)
    nums = re.findall(r"[\d,]+", s)
    if len(nums) < 2:
        return None
    try:
        lo, hi = float(nums[0].replace(",", "")), float(nums[1].replace(",", ""))
    except ValueError:
        return None
    if lo < 1 or hi < 1:
        return None
    if "year" in s.lower() or "annual" in s.lower():
        lo, hi = lo / 12, hi / 12
    if any(x in s.upper() for x in ["SAR", " SR", "SR "]):
        lo, hi = lo / 3.75, hi / 3.75
    return (lo + hi) / 2


def norm_salary_bucket(val) -> str | None:
    """Bucket a salary string into the same bracket labels shown on the dashboard chart."""
    mid = parse_salary_mid(val)
    if mid is None:
        return None
    for lo, hi, label in zip(SALARY_BUCKET_BINS, SALARY_BUCKET_BINS[1:], SALARY_BUCKET_LABELS):
        if lo <= mid < hi:
            return label
    return None


def norm_sector(val) -> str | None:
    """Consolidate duplicate sector names (e.g. Oil and Gas / Oil & Gas)."""
    if pd.isna(val) or not str(val).strip():
        return None
    s = str(val).strip().lower()
    _ALIASES = {
        "oil and gas": "Oil & Gas",
        "oil & gas": "Oil & Gas",
        "information technology": "Technology",
        "it": "Technology",
        "tech": "Technology",
        "commercial support services": "Commercial Support",
        "business support services": "Business Support",
        "services and support": "Services",
        "services & support": "Services",
    }
    return _ALIASES.get(s, str(val).strip())


# ---------------------------------------------------------------------------
# Arabic-portal signal extractors
# ---------------------------------------------------------------------------

def _lang_signal(text) -> str:
    if pd.isna(text) or not str(text).strip():
        return "unspecified"
    t = str(text).lower()
    ar_req = any(x in t for x in [
        "arabic mandatory", "fluent in arabic", "arabic required",
        "arabic fluency", "إجادة اللغة العربية", "العربية إلزامي",
        "اللغة العربية شرط",
    ])
    en_req = any(x in t for x in [
        "english mandatory", "fluent in english", "english required",
        "english fluency", "إجادة الإنجليزية", "الإنجليزية إلزامي",
    ])
    if ar_req and en_req:  return "both"
    if ar_req:             return "arabic"
    if en_req:             return "english"
    return "unspecified"


_NATIONAL_KW: dict[str, list[str]] = {
    "Qatar":        ["مواطن قطري", "قطري الجنسية", "للقطريين", "qatarization", "qatari national"],
    "UAE":          ["مواطن إماراتي", "إماراتي الجنسية", "للإماراتيين", "emiratization", "emirati national"],
    "Saudi Arabia": ["سعودي الجنسية", "للسعوديين", "مواطن سعودي", "saudization", "saudi national", "nitaqat"],
}


def _national_signal(text, country: str) -> bool:
    if pd.isna(text) or not str(text).strip():
        return False
    t = str(text).lower()
    return any(k.lower() in t for k in _NATIONAL_KW.get(country, []))


def _remote_signal(text) -> bool:
    if pd.isna(text) or not str(text).strip():
        return False
    t = str(text).lower()
    return any(x in t for x in ["remote", "work from home", "hybrid", "wfh",
                                  "عن بعد", "من المنزل", "عمل عن بعد"])


# ---------------------------------------------------------------------------
# Filename parser
# ---------------------------------------------------------------------------

def parse_file_info(filepath: str | Path) -> dict:
    """
    Parse a Bayt.com or LinkedIn filename into metadata.

    Accepted formats
    ----------------
    bayt_jobs_{Country}_{Day}_{Month}_{Year}.xlsx          ← Bayt EN posting data
    bayt_jobs_{Country}_AR_{Day}_{Month}_{Year}.xlsx       ← Bayt Arabic portal data
    linkedin_jobs_{Country}_{Day}_{Month}_{Year}_*.xlsx    ← LinkedIn (any trailing suffix)
    anything_else.xlsx                                     ← fallback (unknown country)

    Returns
    -------
    dict with keys: country, timeline, dump_id, dump_label, is_ar, source
    """
    stem  = Path(filepath).stem
    lower = stem.lower()

    # Detect source + strip its prefix
    if lower.startswith("bayt_jobs_"):
        source, rest = "Bayt", stem[len("bayt_jobs_"):]
    elif lower.startswith("linkedin_jobs_"):
        source, rest = "LinkedIn", stem[len("linkedin_jobs_"):]
    else:
        # Legacy / unknown format — derive timeline from filename heuristically
        tl = _parse_timeline_fallback(stem)
        return {
            "country":    "Unknown",
            "timeline":   tl,
            "dump_id":    re.sub(r"[^a-z0-9]", "_", lower),
            "dump_label": stem,
            "is_ar":      False,
            "source":     "Unknown",
        }

    # Detect and strip AR flag (Bayt only; LinkedIn has no Arabic portal)
    is_ar = bool(re.search(r"_AR_", rest, re.IGNORECASE))
    if is_ar:
        rest = re.sub(r"_AR_", "_", rest, count=1, flags=re.IGNORECASE)

    # Pattern: {Country_Words}_{day}_{month}_{year} — ignore any trailing suffix
    # (LinkedIn files carry e.g. "_LLM_Enriched_22_Jun_2026" after the scrape date).
    m = re.match(r"^(.+?)_(\d{1,2})_([A-Za-z]{3,9})_(\d{4})(?:_.*)?$", rest)
    if not m:
        tl = _parse_timeline_fallback(stem)
        return {
            "country":    "Unknown",
            "timeline":   tl,
            "dump_id":    re.sub(r"[^a-z0-9]", "_", lower),
            "dump_label": stem,
            "is_ar":      is_ar,
            "source":     source,
        }

    country_raw = m.group(1)                                        # e.g. "Saudi_Arabia"
    month_key   = m.group(3).lower()                               # e.g. "jun"
    month_abbr  = _MONTH_MAP.get(month_key, m.group(3).capitalize())  # e.g. "Jun"
    year        = m.group(4)                                        # e.g. "2026"

    country  = country_raw.replace("_", " ")                       # "Saudi Arabia"
    timeline = f"{month_abbr} {year}"                              # "Jun 2026"

    # Dump id groups all files of one (source, country, month). For LinkedIn this
    # deliberately merges the 1-June and 7-June scrapes into a single dataset
    # (duplicate job_ids are removed later in load_all).
    if source == "LinkedIn":
        dump_id    = f"{country_raw.lower()}_linkedin_{month_abbr.lower()}_{year}"
        dump_label = f"{country} {timeline} (LinkedIn)"
    else:
        dump_id    = f"{country_raw.lower()}_{month_abbr.lower()}_{year}"
        dump_label = f"{country} {timeline}"

    return {
        "country":    country,
        "timeline":   timeline,
        "dump_id":    dump_id,
        "dump_label": dump_label,
        "is_ar":      is_ar,
        "source":     source,
    }


def _parse_timeline_fallback(stem: str) -> str:
    """Heuristic timeline extraction from arbitrary filenames."""
    s = stem.lower()
    year_m = re.search(r"(?<!\d)(20\d{2})(?!\d)", s)
    year = year_m.group(1) if year_m else None
    # Split on separators and check each token — avoids variable-width lookbehind
    tokens = set(re.split(r"[_\-\s\d]+", s))
    for key, abbr in _MONTH_MAP.items():
        if key in tokens:
            return f"{abbr} {year}" if year else abbr
    return stem


# ---------------------------------------------------------------------------
# Column alias resolver
# ---------------------------------------------------------------------------

def _build_rename_map(actual_columns: list[str]) -> dict[str, str]:
    lower_to_actual = {c.lower(): c for c in actual_columns}
    rename: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias.lower() in lower_to_actual:
                rename[lower_to_actual[alias.lower()]] = canonical
                break
    return rename


def _load_file(path: Path, compact: bool = False) -> pd.DataFrame:
    usecols = None
    if compact:
        excluded = {alias.lower() for alias in COLUMN_ALIASES.get("original_content", [])}
        excluded.add("llm_error")
        usecols = lambda column: str(column).strip().lower() not in excluded
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path, usecols=usecols)
    elif path.suffix.lower() == ".csv":
        return pd.read_csv(path, usecols=usecols)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def _load_ar_signals_compact(path: Path, country: str) -> pd.DataFrame:
    """Stream an Arabic workbook into small derived signals, not raw page text."""
    if path.suffix.lower() != ".xlsx":
        raw = _load_file(path)
        rename_map = _build_rename_map(list(raw.columns))
        frame = raw.rename(columns=rename_map)
        ar_col = next(
            (column for column in frame.columns
             if any(key in str(column).lower() for key in ("original", "ar_content", "page_content"))),
            None,
        )
        if ar_col is None or "job_id" not in frame.columns:
            return pd.DataFrame()
        return pd.DataFrame({
            "job_id": frame["job_id"],
            "_lang_signal": frame[ar_col].map(_lang_signal),
            "_national_signal": frame[ar_col].map(lambda value: _national_signal(value, country)),
            "_remote_signal": frame[ar_col].map(_remote_signal),
            "_has_ar_content": frame[ar_col].notna(),
        }).drop_duplicates("job_id")

    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=True)
        headers = [str(value or "") for value in next(rows)]
        rename_map = _build_rename_map(headers)
        job_header = next((header for header, canonical in rename_map.items() if canonical == "job_id"), None)
        ar_header = next(
            (header for header in headers
             if any(key in header.lower() for key in ("original", "ar_content", "page_content"))),
            None,
        )
        if job_header is None or ar_header is None:
            return pd.DataFrame()

        job_index = headers.index(job_header)
        ar_index = headers.index(ar_header)
        records: list[dict] = []
        for row in rows:
            job_id = row[job_index] if job_index < len(row) else None
            content = row[ar_index] if ar_index < len(row) else None
            records.append({
                "job_id": job_id,
                "_lang_signal": _lang_signal(content),
                "_national_signal": _national_signal(content, country),
                "_remote_signal": _remote_signal(content),
                "_has_ar_content": content is not None and bool(str(content).strip()),
            })
        return pd.DataFrame.from_records(records).drop_duplicates("job_id")
    finally:
        workbook.close()


# ---------------------------------------------------------------------------
# Timeline sort helper
# ---------------------------------------------------------------------------

def _sort_timelines(timelines: list[str]) -> list[str]:
    return sort_timelines(timelines)


def sort_timelines(timelines: list[str]) -> list[str]:
    """
    Sort timeline labels chronologically (earliest first).
    Uses (year, month_index) key — never alphabetical.
    Public version — import this wherever timeline lists need ordering.

    Examples
    --------
    ['May 2026', 'Nov 2025', 'Feb 2026']  →  ['Nov 2025', 'Feb 2026', 'May 2026']
    """
    def _key(tl: str):
        parts = tl.split()
        try:
            return (int(parts[1]) if len(parts) > 1 else 0,
                    _MONTH_ORDER.get(parts[0], 99))
        except Exception:
            return (9999, 99)
    return sorted(timelines, key=_key)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _source_files(data_dir: Path) -> list[Path]:
    return sorted(
        f for f in list(data_dir.glob("*.xlsx")) + list(data_dir.glob("*.csv"))
        if not f.name.startswith("~$")
    )


def _source_fingerprint(files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode("utf-8"))
        digest.update(str(path.stat().st_size).encode("ascii"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()[:20]


def _load_runtime_snapshot(data_dir: Path, files: list[Path]) -> tuple[pd.DataFrame, list[str]] | None:
    parquet_path = data_dir / RUNTIME_PARQUET
    manifest_path = data_dir / RUNTIME_MANIFEST
    if not parquet_path.exists() or not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != RUNTIME_SCHEMA_VERSION:
            return None
        if manifest.get("source_fingerprint") != _source_fingerprint(files):
            return None
        frame = pd.read_parquet(parquet_path)
        if len(frame) != int(manifest.get("record_count", -1)):
            return None
        return frame, [str(value) for value in manifest.get("timelines", [])]
    except Exception:
        return None


def build_runtime_snapshot(data_dir: Path = DATA_DIR) -> tuple[Path, Path, int]:
    """Process source workbooks once into a compact, version-checked artifact."""
    files = _source_files(data_dir)
    frame, timelines = load_all(data_dir, compact=True, use_runtime=False)
    # Excel frequently mixes numeric Bayt IDs with string LinkedIn IDs in one
    # logical column. Arrow requires a stable physical type, so normalize only
    # object columns while preserving missing values as nulls.
    for column in frame.columns:
        if pd.api.types.is_object_dtype(frame[column].dtype) or pd.api.types.is_string_dtype(frame[column].dtype):
            frame[column] = frame[column].map(
                lambda value: None if pd.isna(value) else str(value)
            )
    parquet_path = data_dir / RUNTIME_PARQUET
    manifest_path = data_dir / RUNTIME_MANIFEST
    frame.to_parquet(parquet_path, index=False, compression="zstd")
    manifest = {
        "schema_version": RUNTIME_SCHEMA_VERSION,
        "source_fingerprint": _source_fingerprint(files),
        "record_count": len(frame),
        "timelines": timelines,
        "sources": [path.name for path in files],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return parquet_path, manifest_path, len(frame)


def load_all(
    data_dir: Path = DATA_DIR,
    compact: bool = False,
    use_runtime: bool = True,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Scan data_dir for all Excel/CSV files.

    - EN files  → primary posting data, normalised + enriched
    - AR files  → bilingual signal extraction only (language, nationalization, remote)
                  merged into EN rows by job_id where available

    `compact=True` keeps derived Arabic signals but drops large raw page-text
    columns before frames accumulate. Use it for memory-constrained API hosts;
    offline index builders keep the default full-text dataframe.

    Returns (merged_df, sorted_timelines_list).
    The DataFrame contains all canonical columns plus:
      _timeline, _country, _dump_id, _dump_label, _source_file
      _employment_norm, _career_norm, _sector_norm
      _lang_signal, _national_signal, _remote_signal  (from AR portal)
    """
    all_files = _source_files(data_dir)
    if not all_files:
        raise FileNotFoundError(f"No data files found in {data_dir}")

    if compact and use_runtime:
        runtime = _load_runtime_snapshot(data_dir, all_files)
        if runtime is not None:
            return runtime

    # Separate EN and AR files
    en_entries: list[tuple[Path, dict]] = []
    ar_lookup:  dict[str, Path] = {}   # dump_id → AR file path

    for f in all_files:
        info = parse_file_info(f)
        if info["is_ar"]:
            ar_lookup[info["dump_id"]] = f
        else:
            en_entries.append((f, info))

    if not en_entries:
        raise FileNotFoundError("No EN (non-AR) data files found.")

    frames: list[pd.DataFrame] = []

    for f, info in en_entries:
        raw = _load_file(f, compact=compact)
        rename_map = _build_rename_map(list(raw.columns))
        df = raw.rename(columns=rename_map)

        # Inject file-level metadata
        df["_timeline"]   = info["timeline"]
        df["_country"]    = info["country"]
        df["_dump_id"]    = info["dump_id"]
        df["_dump_label"] = info["dump_label"]
        df["_source_file"] = f.name
        df["_source"]      = info["source"]   # "Bayt" | "LinkedIn"

        # Substring-normalised columns (fix for wrong-answer bug)
        if "employment_type" in df.columns:
            df["_employment_norm"] = df["employment_type"].apply(norm_employment)
        else:
            df["_employment_norm"] = None

        if "career_level" in df.columns:
            df["_career_norm"] = df["career_level"].apply(norm_career)
        else:
            df["_career_norm"] = None

        if "category" in df.columns:
            df["_sector_norm"] = df["category"].apply(norm_sector)
        else:
            df["_sector_norm"] = None

        if "salary" in df.columns:
            df["_salary_bucket_norm"] = df["salary"].apply(norm_salary_bucket)
        else:
            df["_salary_bucket_norm"] = None

        # Try to merge AR bilingual signals
        ar_path = ar_lookup.get(info["dump_id"])
        if ar_path:
            try:
                if compact:
                    ar_sub = _load_ar_signals_compact(ar_path, info["country"])
                    if not ar_sub.empty and "job_id" in df.columns:
                        def _job_key(value):
                            if pd.isna(value):
                                return None
                            text = str(value).strip()
                            return text[:-2] if text.endswith(".0") else text

                        df["_compact_job_key"] = df["job_id"].map(_job_key)
                        ar_sub["_compact_job_key"] = ar_sub["job_id"].map(_job_key)
                        df = (
                            df.merge(
                                ar_sub.drop(columns="job_id"),
                                on="_compact_job_key",
                                how="left",
                            )
                            .drop(columns="_compact_job_key")
                        )
                        df["_lang_signal"] = df["_lang_signal"].fillna("unspecified")
                        for signal in ("_national_signal", "_remote_signal", "_has_ar_content"):
                            df[signal] = df[signal].fillna(False).astype(bool)
                    else:
                        _add_empty_ar_cols(df)
                        df["_has_ar_content"] = False
                    ar_df = None
                else:
                    ar_raw    = _load_file(ar_path)
                    ar_rename = _build_rename_map(list(ar_raw.columns))
                    ar_df     = ar_raw.rename(columns=ar_rename)

                # Identify the Arabic content column
                ar_col = next(
                    (c for c in ar_df.columns
                     if any(k in c.lower() for k in ["original", "ar_content", "page_content"])),
                    None,
                ) if ar_df is not None else None

                if not compact and ar_col and "job_id" in ar_df.columns and "job_id" in df.columns:
                    ar_sub = (ar_df[["job_id", ar_col]]
                              .rename(columns={ar_col: "_ar_content"})
                              .drop_duplicates("job_id"))
                    df = df.merge(ar_sub, on="job_id", how="left")
                    df["_lang_signal"]     = df["_ar_content"].apply(_lang_signal)
                    df["_national_signal"] = df.apply(
                        lambda r: _national_signal(r.get("_ar_content"), info["country"]),
                        axis=1,
                    )
                    df["_remote_signal"]   = df["_ar_content"].apply(_remote_signal)
                elif not compact:
                    _add_empty_ar_cols(df)
            except Exception:
                _add_empty_ar_cols(df)
                if compact:
                    df["_has_ar_content"] = False
        else:
            _add_empty_ar_cols(df)

        # LinkedIn carries an explicit remote flag — use it directly (Bayt only
        # has it via the AR portal signal, handled above).
        if info["source"] == "LinkedIn":
            remote_col = next((c for c in df.columns if c.lower() == "is_remote"), None)
            if remote_col is not None:
                df["_remote_signal"] = (
                    df[remote_col].astype(str).str.strip().str.lower()
                    .isin(["true", "1", "yes", "remote"])
                )

        if compact:
            if "_ar_content" in df.columns:
                df["_has_ar_content"] = df["_ar_content"].notna()
            df = df.drop(
                columns=["_ar_content", "original_content", "llm_error"],
                errors="ignore",
            )

        frames.append(df)

    merged = pd.concat(frames, ignore_index=True)

    # Remove duplicate postings within a dataset. This collapses the overlapping
    # LinkedIn 1-June / 7-June scrapes (merged into one dump_id) by job_id.
    # Rows without a job_id are kept as-is (never treated as duplicates).
    if "job_id" in merged.columns and "_dump_id" in merged.columns:
        has_id = merged["job_id"].notna()
        deduped = (merged[has_id]
                   .drop_duplicates(subset=["_dump_id", "job_id"], keep="first"))
        merged = (pd.concat([deduped, merged[~has_id]], ignore_index=True)
                  .reset_index(drop=True))

    timelines = _sort_timelines(
        list({t for df in frames for t in df["_timeline"].dropna().unique()})
    )
    return merged, timelines


def _add_empty_ar_cols(df: pd.DataFrame):
    df["_ar_content"]      = None
    df["_lang_signal"]     = "unspecified"
    df["_national_signal"] = False
    df["_remote_signal"]   = False
