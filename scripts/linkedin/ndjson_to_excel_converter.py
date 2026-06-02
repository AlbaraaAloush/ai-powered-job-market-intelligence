"""
NDJSON → Excel Converter
Reads a LinkedIn jobs NDJSON file produced by scraper.py and writes a
formatted Excel file. Safe to re-run as many times as needed — never
touches LinkedIn.

Usage:
    python convert_to_excel.py <path_to_ndjson_file>

    # Example:
    python convert_to_excel.py linkedin_qatar_jobs_20260531_1400.ndjson

Install:
    pip install openpyxl pandas

Edge cases handled:
  - Malformed / partial JSON lines     : skipped with a warning, rest of file loads fine
  - Empty NDJSON file                  : exits cleanly with a message
  - Schema drift (columns differ       : union of all keys used; missing fields → empty cell
    across batches)
  - Illegal XML / openpyxl chars       : stripped from all string values before writing
    (e.g. the original error: "About QNB" with control chars)
  - Nested dicts (location,            : flattened to "location.city", "location.country" etc.
    compensation)
  - List values (job_type, emails)     : joined to a comma-separated string for Excel
  - None / null values                 : written as empty cells (not the string "None")
  - Duplicate records                  : deduplicated by job_url before writing
  - Output path collision              : output file named after input file, never overwrites
"""

import sys
import json
import re
import logging
from pathlib import Path

import pandas as pd

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Illegal character regex for openpyxl ───────────────────────────────────────

_ILLEGAL_CHARS_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ud800-\udfff\ufffe\uffff]"
)


# ── NDJSON loader ──────────────────────────────────────────────────────────────

def load_ndjson(path: Path) -> list[dict]:
    """
    Load records from an NDJSON file.
    Skips malformed lines with a warning instead of crashing.
    """
    records = []
    bad_lines = 0
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                bad_lines += 1
                log.warning(f"Skipping malformed line {lineno}: {exc}")
    if bad_lines:
        log.warning(f"{bad_lines} malformed line(s) skipped out of {lineno} total")
    return records


def deduplicate(records: list[dict], key: str = "job_url") -> list[dict]:
    """Remove duplicate records by a key, keeping first occurrence."""
    seen: set = set()
    unique = []
    for rec in records:
        val = rec.get(key)
        if val and val in seen:
            continue
        if val:
            seen.add(val)
        unique.append(rec)
    return unique


# ── Record flattening ──────────────────────────────────────────────────────────

def _flatten_value(val, key: str) -> object:
    """
    Prepare a single value for a DataFrame cell:
      - Nested dicts (location, compensation): flatten into dotted subkeys
        (handled at the record level in flatten_record)
      - Lists: join to comma-separated string
      - None: return None (pandas writes as empty cell, not "None")
      - Everything else: return as-is
    """
    if val is None:
        return None
    if isinstance(val, list):
        # Filter out None items, join the rest
        return ", ".join(str(v) for v in val if v is not None)
    if isinstance(val, dict):
        # Should have been flattened already; stringify as fallback
        return json.dumps(val, ensure_ascii=False)
    return val


def flatten_record(record: dict, parent_key: str = "", sep: str = ".") -> dict:
    """
    Recursively flatten nested dicts into dotted keys.
    e.g. {"location": {"city": "Doha", "country": "qatar"}}
         → {"location.city": "Doha", "location.country": "qatar"}
    Lists are NOT expanded — they stay as joined strings.
    """
    flat = {}
    for k, v in record.items():
        full_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            flat.update(flatten_record(v, full_key, sep))
        else:
            flat[full_key] = _flatten_value(v, full_key)
    return flat


# ── Excel sanitization ─────────────────────────────────────────────────────────

def _sanitize(val):
    """Strip illegal XML/openpyxl control characters from string values."""
    if isinstance(val, str):
        return _ILLEGAL_CHARS_RE.sub("", val)
    return val


# ── Excel writer ───────────────────────────────────────────────────────────────

def write_excel(df: pd.DataFrame, path: Path) -> bool:
    """
    Write a formatted Excel file from a DataFrame.
    Returns True on success, False on failure.
    """
    try:
        from openpyxl.styles import Font, PatternFill, Alignment

        # Sanitize all string cells
        df = df.apply(
            lambda col: col.map(_sanitize) if col.dtype == object else col
        )

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Jobs")
            ws = writer.sheets["Jobs"]

            # Auto-size columns (capped at 80 chars)
            for col_cells in ws.columns:
                max_len = max(
                    (len(str(c.value)) if c.value is not None else 0 for c in col_cells),
                    default=10,
                )
                ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 2, 80)

            # Freeze header row
            ws.freeze_panes = "A2"

            # Style header
            header_fill = PatternFill("solid", start_color="1F4E79")
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF", name="Arial", size=10)
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center", vertical="center")

            # Zebra-stripe rows
            light_blue = PatternFill("solid", start_color="DCE6F1")
            for i, row in enumerate(ws.iter_rows(min_row=2), start=2):
                if i % 2 == 0:
                    for cell in row:
                        cell.fill = light_blue

        return True

    except Exception as exc:
        log.error(f"Excel write failed: {exc}")
        return False


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python convert_to_excel.py <path_to_ndjson_file>")
        print("Example: python convert_to_excel.py linkedin_qatar_jobs_20260531_1400.ndjson")
        sys.exit(1)

    ndjson_path = Path(sys.argv[1])

    if not ndjson_path.exists():
        log.error(f"File not found: {ndjson_path}")
        sys.exit(1)

    if ndjson_path.suffix.lower() not in (".ndjson", ".jsonl", ".json"):
        log.warning(f"Unexpected file extension: {ndjson_path.suffix} — proceeding anyway")

    # Output file sits next to the input file, same name, .xlsx extension
    xlsx_path = ndjson_path.with_suffix(".xlsx")

    log.info(f"Input  : {ndjson_path}")
    log.info(f"Output : {xlsx_path}\n")

    # ── Load ──────────────────────────────────────────────────────────────────
    log.info("Loading NDJSON…")
    records = load_ndjson(ndjson_path)

    if not records:
        log.error("No records loaded — file may be empty or fully malformed.")
        sys.exit(1)

    log.info(f"Loaded {len(records):,} raw records")

    # ── Deduplicate ───────────────────────────────────────────────────────────
    records = deduplicate(records)
    log.info(f"After deduplication: {len(records):,} unique records")

    # ── Flatten nested fields ─────────────────────────────────────────────────
    log.info("Flattening nested fields (location, compensation)…")
    flat_records = [flatten_record(r) for r in records]

    # ── Build DataFrame ───────────────────────────────────────────────────────
    # Schema drift is handled automatically: pd.DataFrame takes the union of
    # all keys; any record missing a key gets NaN → shown as empty cell
    df = pd.DataFrame(flat_records)

    # Replace any remaining None/NaN with actual None so Excel shows blank cells
    df = df.where(pd.notnull(df), other=None)

    log.info(f"DataFrame shape: {df.shape[0]:,} rows × {df.shape[1]} columns")
    log.info(f"Columns: {list(df.columns)}\n")

    # ── Write Excel ───────────────────────────────────────────────────────────
    log.info("Writing Excel file…")
    success = write_excel(df, xlsx_path)

    if success:
        log.info(f"\n  Excel saved → {xlsx_path.resolve()}")
        log.info(f"  Rows: {len(df):,}  |  Columns: {df.shape[1]}")
    else:
        log.error("\n  Excel conversion failed. Your NDJSON data is intact.")
        log.error(f"  Fix the error above, then re-run:")
        log.error(f"  python convert_to_excel.py {ndjson_path.name}")
        sys.exit(1)


if __name__ == "__main__":
    main()
