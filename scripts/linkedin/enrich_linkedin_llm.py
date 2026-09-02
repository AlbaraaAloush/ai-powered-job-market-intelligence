"""Enrich a LinkedIn jobs XLSX/NDJSON file with LLM-extracted fields.

Reads an existing LinkedIn jobs file (XLSX or NDJSON) — sourced from any
country/market, not just Saudi Arabia — and for every row that has a
non-empty Job_Description, calls an OpenAI model to extract up to 8
structured fields that are currently missing or blank:

    Salary_Range_USD        Years_of_Experience    Company_Size
    Job_Skills               Required_Qualifications Gender
    Education_Level          Language_Requirement

Rules:
  - Rows with a null / empty Job_Description are skipped entirely (no API call).
  - Existing non-null values are NEVER overwritten (field-level guard).
  - Job_ID is a unique identifier and is NEVER enriched, modified, or
    overwritten under any circumstance.
  - Post_Date is a plain passthrough input field — it is not derived or
    LLM-enriched.
  - Results are checkpointed to JSON every --checkpoint rows (default: 25) so a
    crash never loses more than one checkpoint window of work.
  - Every failed row records its error in an ``llm_error`` column; the run
    never aborts due to a single row failure.
  - Supports resuming: re-run on the checkpoint JSON with --from-json to skip
    rows already fully enriched.

Outputs:
  <stem>_LLM_Enriched_<DD_Mon_YYYY>.{xlsx,json}

Usage:
    python enrich_linkedin_llm.py input.xlsx
    python enrich_linkedin_llm.py input.xlsx --workers 4 --checkpoint 10
    python enrich_linkedin_llm.py input.ndjson
    python enrich_linkedin_llm.py input.xlsx --openai-model gpt-4o
    python enrich_linkedin_llm.py input.xlsx --no-overwrite false   # force re-extract
    python enrich_linkedin_llm.py --from-json checkpoint.json       # resume from JSON
    python enrich_linkedin_llm.py input.xlsx --dry-run              # no API calls
    python enrich_linkedin_llm.py input.xlsx --max-rows 10          # test on first N
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import logging
import math
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

# Fields the LLM is asked to extract. Job_ID is intentionally absent — it is
# a unique identifier and must never be enriched, modified, or overwritten.
# Post_Date is also absent — it is a plain passthrough input field, not
# derived or LLM-enriched.
LLM_TARGET_FIELDS: list[str] = [
    "Salary_Range_USD",
    "Years_of_Experience",
    "Company_Size",
    "Job_Skills",
    "Required_Qualifications",
    "Gender",
    "Education_Level",
    "Language_Requirement",
]

# All columns that must exist in the output (in the desired order).
OUTPUT_COLUMNS: list[str] = [
    "Job_ID",
    "Job_Title",
    "Company_Name",
    "Job_Category",
    "Job_Location",
    "Salary_Range_USD",
    "Employment_Type",
    "Career_Level",
    "Years_of_Experience",
    "Company_Size",
    "Job_Description",
    "Job_Skills",
    "Required_Qualifications",
    "Gender",
    "Post_Date",
    "Education_Level",
    "Language_Requirement",
    "Is_Remote",
    "URL",
    "llm_error",
]

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_WORKERS = 8
DEFAULT_CHECKPOINT = 25

# XLSX cell safety
_XLSX_ILLEGAL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
_XLSX_CELL_LIMIT = 32_767

log = logging.getLogger("linkedin-llm-enricher")

# ──────────────────────────────────────────────────────────────────────────────
# LLM prompt
# ──────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You extract structured fields from LinkedIn job postings. Postings may come
from any country or market — do not assume a specific region, currency, or
language unless the posting itself indicates one.

Output ONLY a single JSON object with exactly these keys:
Salary_Range_USD, Years_of_Experience, Company_Size, Job_Skills,
Required_Qualifications, Gender, Education_Level, Language_Requirement.

Rules:
- All values are either a non-empty string or null. Never use arrays or objects.
- If a field cannot be confidently inferred from the provided text, return null.
- Salary_Range_USD: is "X-Y USD/month" or "X USD/month" if a salary is
  stated; otherwise null. Convert other currencies to USD using these rough
  rates: 1 QAR = 0.27 USD, 1 SAR = 0.27 USD, 1 AED = 0.27 USD, 1 EUR = 1.08
  USD, 1 GBP = 1.27 USD. Round to nearest 10.
- Years_of_Experience: is a brief phrase like "2-5 years", "10+ years",
  "Minimum 2 years" or null.
- Company_Size: short phrase like "50-99 employees", "1,001-5,000 employees",
  "10,000+ employees", or null. Use standard LinkedIn size brackets when the
  description mentions headcount or a well-known company size.
- Job_Skills: skills separated by "; ". Short English phrases (e.g. "Python; AutoCAD;
  Project Management"). null if none mentioned.
- Required_Qualifications: qualifications separated by "; " (e.g.
  "Bachelor's in Civil Engineering; professional engineering registration;
  5+ years experience"). null if none mentioned.
- Gender: "Male", "Female", or "Any". Only set if the posting explicitly states a
  gender preference; otherwise null.
- Education_Level: highest required degree as a short phrase —
  "High School", "Diploma", "Bachelor", "Master", "PhD" or null.
- Language_Requirement: is a short English phrase (e.g. "Arabic fluency
  mandatory", "Excellent English communication") or null.
"""


def _build_user_prompt(row: dict[str, Any]) -> str:
    """Construct the user-turn prompt from a job row dict."""
    lines = [
        f"Job Title: {row.get('Job_Title') or ''}",
        f"Company: {row.get('Company_Name') or ''}",
        f"Location: {row.get('Job_Location') or ''}",
        f"Employment Type: {row.get('Employment_Type') or ''}",
        f"Career Level: {row.get('Career_Level') or ''}",
        "",
        "=== Job Description ===",
        str(row.get("Job_Description") or ""),
    ]
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# JSON schema for structured output
# ──────────────────────────────────────────────────────────────────────────────

_JSON_SCHEMA = {
    "name": "LinkedInJobExtraction",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": LLM_TARGET_FIELDS,
        "properties": {f: {"type": ["string", "null"]} for f in LLM_TARGET_FIELDS},
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# OpenAI client helpers
# ──────────────────────────────────────────────────────────────────────────────


def _build_client(api_key: Optional[str]):
    try:
        from openai import OpenAI
    except ImportError:
        log.error("openai package not installed. Run: pip install openai")
        sys.exit(1)
    return OpenAI(api_key=api_key) if api_key else OpenAI()


def _call_llm(
    client,
    model: str,
    row: dict[str, Any],
    max_retries: int = 3,
    base_delay: float = 2.0,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """Call the LLM and return (extracted_dict, error_message).

    Retries on rate-limit (429) and server errors (5xx) with exponential
    back-off + jitter.  Returns (None, error_str) on final failure.
    """
    user_prompt = _build_user_prompt(row)

    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                max_tokens=1000,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_schema", "json_schema": _JSON_SCHEMA},
            )
            raw = resp.choices[0].message.content or "{}"
            # Strip accidental markdown fences
            raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
            raw = re.sub(r"```\s*$", "", raw.strip())
            data = json.loads(raw)
            return data, None

        except json.JSONDecodeError as e:
            err = f"JSON decode error: {e}"
            log.warning("Row %s attempt %d/%d: %s", row.get("Job_ID"), attempt, max_retries, err)
            # Don't retry JSON errors — the model produced garbage; move on.
            return None, err

        except Exception as e:
            err_str = str(e)
            is_rate_limit = "429" in err_str or "rate_limit" in err_str.lower()
            is_server_err = any(c in err_str for c in ("500", "502", "503", "504"))

            log.warning(
                "Row %s attempt %d/%d: %s",
                row.get("Job_ID"), attempt, max_retries, err_str,
            )

            if attempt < max_retries and (is_rate_limit or is_server_err):
                delay = base_delay * (2 ** (attempt - 1)) + (time.time() % 1.0)
                log.info("Backing off %.1fs before retry...", delay)
                time.sleep(delay)
                continue

            return None, err_str

    return None, "Max retries exhausted"


# ──────────────────────────────────────────────────────────────────────────────
# Row-level enrichment
# ──────────────────────────────────────────────────────────────────────────────

_thread_local = threading.local()


def _get_client(api_key: Optional[str], model: str):
    """Return a thread-local OpenAI client."""
    if not hasattr(_thread_local, "client"):
        _thread_local.client = _build_client(api_key)
    return _thread_local.client


def _needs_enrichment(row: dict[str, Any], no_overwrite: bool) -> bool:
    """Return True if the row has at least one LLM target field that needs filling."""
    desc = row.get("Job_Description")
    if desc is None or (isinstance(desc, float) and math.isnan(desc)):
        return False
    if isinstance(desc, str) and desc.strip() == "":
        return False

    if not no_overwrite:
        return True  # --no-overwrite false: always re-extract

    # At least one target field is empty
    for field in LLM_TARGET_FIELDS:
        val = row.get(field)
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return True
        if isinstance(val, str) and val.strip() == "":
            return True
    return False


def enrich_row(
    row: dict[str, Any],
    api_key: Optional[str],
    model: str,
    no_overwrite: bool,
    dry_run: bool,
) -> dict[str, Any]:
    """Enrich a single row in-place and return it."""
    row = dict(row)  # work on a copy
    original_job_id = row.get("Job_ID")  # immutable — guarded below

    if not _needs_enrichment(row, no_overwrite):
        row["Job_ID"] = original_job_id
        return row

    if dry_run:
        log.debug("DRY-RUN: would call LLM for %s", row.get("Job_ID"))
        row["Job_ID"] = original_job_id
        return row

    client = _get_client(api_key, model)
    extracted, error = _call_llm(client, model, row)

    if error:
        row["llm_error"] = error
        row["Job_ID"] = original_job_id
        log.warning("Enrichment failed for %s: %s", row.get("Job_ID"), error)
        return row

    # Apply extracted values — only fill empty fields when no_overwrite is True
    for field in LLM_TARGET_FIELDS:
        if field not in extracted:
            continue
        new_val = extracted[field]
        if new_val is None:
            continue
        if isinstance(new_val, str) and new_val.strip() == "":
            continue

        existing = row.get(field)
        already_filled = (
            existing is not None
            and not (isinstance(existing, float) and math.isnan(existing))
            and not (isinstance(existing, str) and existing.strip() == "")
        )
        if already_filled and no_overwrite:
            log.debug(
                "Keeping existing value for %s[%s]='%s'",
                row.get("Job_ID"), field, existing,
            )
            continue

        row[field] = new_val

    # Job_ID is a unique identifier and must never be touched by enrichment,
    # regardless of what the LLM returned or what --no-overwrite is set to.
    row["Job_ID"] = original_job_id
    return row


# ──────────────────────────────────────────────────────────────────────────────
# I/O helpers
# ──────────────────────────────────────────────────────────────────────────────


def load_input(path: Path) -> list[dict[str, Any]]:
    """Load XLSX or NDJSON input into a list of row dicts."""
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str)
        # Preserve boolean Is_Remote correctly
        records = df.where(pd.notna(df), None).to_dict(orient="records")
        return records
    elif suffix in (".ndjson", ".jsonl"):
        records = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records
    elif suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
        raise ValueError(f"JSON file must contain a top-level array, got {type(payload)}")
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Use .xlsx, .ndjson, or .json")


def _xlsx_safe(value: Any) -> Any:
    if isinstance(value, str):
        clean = _XLSX_ILLEGAL_RE.sub("", value)
        if len(clean) > _XLSX_CELL_LIMIT:
            clean = clean[: _XLSX_CELL_LIMIT - 3] + "..."
        return clean
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def write_xlsx(records: list[dict[str, Any]], path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    # Determine actual columns: OUTPUT_COLUMNS first, then any extras
    all_keys: list[str] = list(OUTPUT_COLUMNS)
    for rec in records:
        for k in rec:
            if k not in all_keys:
                all_keys.append(k)

    wb = Workbook()
    ws = wb.active
    ws.title = "Jobs"

    ws.append(all_keys)
    for cell in ws[1]:
        cell.font = Font(bold=True, name="Arial")

    for rec in records:
        row = [_xlsx_safe(rec.get(col)) for col in all_keys]
        ws.append(row)

    # Column widths and wrapping
    wide_cols = {
        "Job_Description": 70,
        "Job_Skills": 45,
        "Required_Qualifications": 45,
        "llm_error": 40,
        "URL": 50,
    }
    wrap_cols = {"Job_Description", "Job_Skills", "Required_Qualifications"}
    for idx, col in enumerate(all_keys, start=1):
        letter = ws.cell(row=1, column=idx).column_letter
        ws.column_dimensions[letter].width = wide_cols.get(col, 22)
        ws.column_dimensions[letter].auto_size = False
        if col in wrap_cols:
            for cell in ws[letter][1:]:
                cell.alignment = Alignment(wrap_text=True, vertical="top")

    ws.freeze_panes = "A2"
    wb.save(path)
    log.info("Saved XLSX → %s", path)


def write_json(records: list[dict[str, Any]], path: Path) -> None:
    def _serialisable(v: Any) -> Any:
        if isinstance(v, float) and math.isnan(v):
            return None
        return v

    cleaned = [{k: _serialisable(v) for k, v in rec.items()} for rec in records]
    path.write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("Saved JSON  → %s", path)


# ──────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ──────────────────────────────────────────────────────────────────────────────


def _date_stamp() -> str:
    return _dt.datetime.now().strftime("%d_%b_%Y")


def _default_outputs(input_path: Path) -> tuple[Path, Path]:
    stem = re.sub(r"_LLM_Enriched.*$", "", input_path.stem)
    base = f"{stem}_LLM_Enriched_{_date_stamp()}"
    return Path(base + ".xlsx"), Path(base + ".json")


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.lower().startswith("export "):
            line = line[len("export "):].lstrip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _ensure_columns(records: list[dict[str, Any]]) -> None:
    """Add any missing target/output columns to every record (in-place)."""
    needed = set(OUTPUT_COLUMNS) | set(LLM_TARGET_FIELDS)
    for rec in records:
        for col in needed:
            if col not in rec:
                rec[col] = None


def run(args: argparse.Namespace) -> int:
    _load_dotenv()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(threadName)-14s] %(levelname)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    # ── Resolve API key ────────────────────────────────────────────────────────
    api_key = args.openai_api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key and not args.dry_run:
        log.error(
            "OPENAI_API_KEY is not set. "
            "Export it, add it to .env, or pass --openai-api-key."
        )
        return 1

    # ── Load input ─────────────────────────────────────────────────────────────
    if args.from_json:
        input_path = Path(args.from_json)
        log.info("Loading from JSON checkpoint: %s", input_path)
    else:
        input_path = Path(args.input)
        log.info("Loading input: %s", input_path)

    if not input_path.exists():
        log.error("Input file not found: %s", input_path)
        return 1

    records = load_input(input_path)
    log.info("Loaded %d records", len(records))

    _ensure_columns(records)

    # ── Determine output paths ─────────────────────────────────────────────────
    ref_path = Path(args.input) if args.input else input_path
    default_xlsx, default_json = _default_outputs(ref_path)
    out_xlsx = Path(args.out_xlsx) if args.out_xlsx else default_xlsx
    out_json = Path(args.out_json) if args.out_json else default_json

    # ── Cap rows for testing ───────────────────────────────────────────────────
    if args.max_rows is not None:
        records = records[: args.max_rows]
        log.info("Capped to %d rows (--max-rows)", len(records))

    # ── Count what needs enrichment ────────────────────────────────────────────
    pending = [r for r in records if _needs_enrichment(r, args.no_overwrite)]
    skipped_no_desc = sum(
        1 for r in records
        if not str(r.get("Job_Description") or "").strip()
    )
    log.info(
        "Rows: total=%d  pending_llm=%d  skipped_no_description=%d",
        len(records), len(pending), skipped_no_desc,
    )

    # Post_Date is a plain passthrough input field (no derivation needed).

    if args.dry_run:
        log.info("DRY-RUN mode — no API calls will be made.")

    if not pending:
        log.info("Nothing to enrich — all rows already filled or have no description.")
        write_json(records, out_json)
        write_xlsx(records, out_xlsx)
        return 0

    # ── Build a fast-lookup index so worker results can be merged back ─────────
    # Records are mutated in-place via their position in `records`.
    id_to_idx: dict[str, int] = {
        r.get("Job_ID", f"__row_{i}"): i for i, r in enumerate(records)
    }

    # ── Concurrent LLM enrichment ──────────────────────────────────────────────
    done = 0
    errors = 0
    lock = threading.Lock()

    def _process(rec: dict[str, Any]) -> dict[str, Any]:
        return enrich_row(
            rec,
            api_key=api_key,
            model=args.openai_model,
            no_overwrite=args.no_overwrite,
            dry_run=args.dry_run,
        )

    log.info(
        "Starting LLM enrichment: %d rows, %d workers, model=%s",
        len(pending), args.workers, args.openai_model,
    )

    try:
        with ThreadPoolExecutor(
            max_workers=args.workers, thread_name_prefix="llm"
        ) as executor:
            futures = {executor.submit(_process, rec): rec for rec in pending}
            try:
                for future in as_completed(futures):
                    original = futures[future]
                    job_id = original.get("Job_ID", "?")
                    try:
                        enriched = future.result()
                    except Exception as exc:
                        log.error("Unexpected error for %s: %s", job_id, exc)
                        enriched = dict(original)
                        enriched["llm_error"] = f"Unexpected: {exc}"

                    # Merge result back into the master list
                    idx = id_to_idx.get(job_id)
                    if idx is not None:
                        records[idx] = enriched

                    with lock:
                        done += 1
                        if enriched.get("llm_error"):
                            errors += 1

                        if done % 10 == 0 or done == len(pending):
                            log.info(
                                "Progress: %d / %d  (errors=%d)",
                                done, len(pending), errors,
                            )

                        # Checkpoint
                        if done % args.checkpoint == 0:
                            write_json(records, out_json)
                            log.info("Checkpoint saved (%d rows done)", done)

            except KeyboardInterrupt:
                log.warning("Interrupted! Saving partial results...")
                executor.shutdown(wait=False, cancel_futures=True)

    finally:
        # Always write final output
        write_json(records, out_json)
        write_xlsx(records, out_xlsx)

    # ── Summary ────────────────────────────────────────────────────────────────
    enriched_ok = done - errors
    log.info("──────────────────────────────────────────")
    log.info("Done.")
    log.info("  Total rows        : %d", len(records))
    log.info("  LLM calls made    : %d", done)
    log.info("  Successfully enriched : %d", enriched_ok)
    log.info("  Errors            : %d", errors)
    log.info("  Skipped (no desc) : %d", skipped_no_desc)
    log.info("  Output XLSX       : %s", out_xlsx)
    log.info("  Output JSON       : %s", out_json)
    log.info("──────────────────────────────────────────")

    return 0


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Input (mutually exclusive: file path vs --from-json resume)
    input_group = p.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Path to input .xlsx or .ndjson file.",
    )
    input_group.add_argument(
        "--from-json",
        default=None,
        metavar="PATH",
        help="Resume from a JSON checkpoint produced by a previous run.",
    )

    p.add_argument(
        "--openai-api-key",
        default=None,
        help="OpenAI API key. Falls back to OPENAI_API_KEY env var or .env file.",
    )
    p.add_argument(
        "--openai-model",
        default=DEFAULT_MODEL,
        help=f"OpenAI model to use (default: {DEFAULT_MODEL}).",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Concurrent OpenAI request threads (default: {DEFAULT_WORKERS}). "
             "Keep ≤8 to avoid rate-limit storms on free/tier-1 keys.",
    )
    p.add_argument(
        "--checkpoint",
        type=int,
        default=DEFAULT_CHECKPOINT,
        help=f"Save a JSON checkpoint every N completed rows (default: {DEFAULT_CHECKPOINT}).",
    )
    p.add_argument(
        "--no-overwrite",
        dest="no_overwrite",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Do not overwrite existing non-empty field values (default: on). "
             "Pass --no-no-overwrite to force re-extraction of all rows.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse input and log what would happen, but make no API calls.",
    )
    p.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Process only the first N rows (useful for smoke-testing).",
    )
    p.add_argument(
        "--out-xlsx",
        default=None,
        metavar="PATH",
        help="Output XLSX path (default: auto-generated from input filename).",
    )
    p.add_argument(
        "--out-json",
        default=None,
        metavar="PATH",
        help="Output JSON path (default: auto-generated from input filename).",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable DEBUG logging.",
    )

    return p.parse_args()


if __name__ == "__main__":
    sys.exit(run(parse_args()))