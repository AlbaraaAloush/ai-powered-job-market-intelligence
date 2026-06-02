"""
LinkedIn Job Scraper — Multi-Country
Scrapes job postings for one or more countries and saves them
incrementally to NDJSON files (one file per country).

Usage:
    # Scrape a single country (default: Qatar)
    python scraper.py

    # Scrape a specific country
    python scraper.py --country "Saudi Arabia"

    # Scrape multiple countries sequentially
    python scraper.py --country "Qatar" "Saudi Arabia" "UAE"

To convert output to Excel:
    python convert_to_excel.py linkedin_Qatar_jobs_20260531_1400.ndjson

Install:
    pip install python-jobspy

Proxy rotation:
    JobSpy's RotatingProxySession uses itertools.cycle internally.
    Passing a list of proxies means each request automatically picks
    the next proxy in the list — no extra code needed.

    Accepted proxy formats (all four work):
        "user:pass@host:port"           # auto-prefixed with http://
        "http://user:pass@host:port"
        "https://user:pass@host:port"
        "socks5://user:pass@host:port"

Type edge cases handled (verified against installed jobspy/model.py + util.py):
  - date_posted         : datetime.date  → ISO string "YYYY-MM-DD"
  - job_type            : list[JobType] Enum → list of string values
  - compensation        : nested Pydantic model with CompensationInterval Enum
  - location            : nested Pydantic model with Country Enum (tuple values)
  - emails / skills     : list[str] | None → serialized as-is
  - numpy.int64/float64 : cast to Python native int/float
  - numpy.nan / NaT     : replaced with None → JSON null
  - Empty batches       : skipped safely
  - Schema drift        : each record is independent — no shared schema required
  - Illegal XML chars   : NOT stripped here (raw data preserved); handled in converter
"""

import argparse
import json
import math
import time
import random
import logging
import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from jobspy import scrape_jobs

# ── Configuration ──────────────────────────────────────────────────────────────

# Countries to scrape when no --country argument is passed
DEFAULT_COUNTRIES = ["Qatar"]

OUTPUT_DIR        = Path(".")
TARGET_TOTAL      = 20000          # per country
RESULTS_PER_BATCH = 100          # LinkedIn caps ~1k per query; 500 is safer
DELAY_SECONDS     = (20, 40)       # randomized delay between batches (min, max)
DELAY_BETWEEN_COUNTRIES = (60, 90) # extra pause when switching countries
HOURS_OLD         = 720           # only jobs posted in last 30 days

# Broad keywords to cover the full job market in any country.
# LinkedIn requires a search term — there is no "show all" endpoint.
# These 20 keywords collectively cover the vast majority of job categories.
KEYWORDS = [
    "engineer", "manager", "analyst", "developer", "sales",
    "finance", "accounting", "marketing", "operations", "human resources",
    "project manager", "consultant", "nurse", "doctor", "teacher",
    "driver", "technician", "administrator", "procurement", "logistics",
]

# ── Proxy configuration ────────────────────────────────────────────────────────
#
# JobSpy rotates through this list automatically using itertools.cycle.
# Each HTTP request picks the next proxy in the cycle — no extra code needed.
#
# Accepted formats:
#   "user:pass@host:port"           → auto-prefixed with http://
#   "http://user:pass@host:port"
#   "https://user:pass@host:port"
#   "socks5://user:pass@host:port"
#
# Leave as an empty list [] to scrape without proxies (fine for small runs;
# for 5,000+ records per country you will likely get rate-limited without them).
#

PROXIES: list[str] = []

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── JSON serialization ─────────────────────────────────────────────────────────

def _safe_json_value(val):
    """
    Convert any value produced by jobspy + pandas into a JSON-safe Python type.
    Handles every known problematic type confirmed in jobspy/model.py and util.py.
    """
    # None / NaN / NaT → null
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass  # pd.isna() raises on lists/dicts — safe to ignore

    # numpy scalars → Python native types
    if isinstance(val, np.integer):
        return int(val)
    if isinstance(val, np.floating):
        return None if math.isnan(float(val)) else float(val)
    if isinstance(val, np.bool_):
        return bool(val)

    # Python date / datetime (date_posted is datetime.date in jobspy)
    if isinstance(val, datetime.datetime):
        return val.isoformat()
    if isinstance(val, datetime.date):
        return val.isoformat()  # "YYYY-MM-DD"

    # pandas Timestamp
    if isinstance(val, pd.Timestamp):
        return None if pd.isna(val) else val.isoformat()

    # Enums (JobType, CompensationInterval, Country, Site …)
    # Confirmed in util.py: Country values are tuples — take human-readable first element
    if hasattr(val, "value"):
        raw = val.value
        if isinstance(raw, tuple):
            return raw[0]
        return str(raw)

    # Lists (job_type is list[JobType], emails/skills are list[str])
    if isinstance(val, list):
        return [_safe_json_value(item) for item in val]

    # Pydantic models (Location, Compensation) — recurse into their dict
    if hasattr(val, "model_dump"):   # Pydantic v2
        return {k: _safe_json_value(v) for k, v in val.model_dump().items()}
    if hasattr(val, "dict"):         # Pydantic v1
        return {k: _safe_json_value(v) for k, v in val.dict().items()}

    # Strings — returned as-is (illegal chars preserved for raw fidelity)
    if isinstance(val, str):
        return val

    # Unknown types — stringify rather than crash
    return str(val)


def df_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to a list of JSON-safe dicts, one dict per row."""
    return [
        {col: _safe_json_value(row[col]) for col in df.columns}
        for _, row in df.iterrows()
    ]


# ── NDJSON writer ──────────────────────────────────────────────────────────────

def append_to_ndjson(records: list[dict], path: Path) -> None:
    """Append records to an NDJSON file. Each record is one line."""
    if not records:
        return
    try:
        with path.open("a", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        log.error(f"Failed to write to NDJSON: {exc}")


# ── Scraper ────────────────────────────────────────────────────────────────────

def scrape_batch(keyword: str, location: str, results_wanted: int) -> pd.DataFrame:
    """Run one JobSpy scrape for a keyword + location. Returns empty DataFrame on failure."""
    try:
        jobs = scrape_jobs(
            site_name=["linkedin"],
            search_term=keyword,
            location=location,
            results_wanted=results_wanted,
            hours_old=HOURS_OLD,
            linkedin_fetch_description=True,
            # JobSpy's RotatingProxySession cycles through this list automatically.
            # Passing None disables proxy use entirely.
            proxies=PROXIES if PROXIES else None,
            verbose=0,
        )
        return jobs if jobs is not None and not jobs.empty else pd.DataFrame()
    except Exception as exc:
        log.warning(f"Scrape failed for '{keyword}' in '{location}': {exc}")
        return pd.DataFrame()


# ── Per-country scrape ─────────────────────────────────────────────────────────

def scrape_country(country: str) -> None:
    """Run the full keyword-batching loop for a single country."""
    # Sanitize country name for use in filename
    safe_name = country.replace(" ", "_").replace("/", "-")
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    ndjson_path = OUTPUT_DIR / f"linkedin_{safe_name}_jobs_{ts}.ndjson"

    log.info(f"  Country   : {country}")
    log.info(f"  Target    : {TARGET_TOTAL:,} jobs")
    log.info(f"  Proxies   : {len(PROXIES)} configured" if PROXIES else "  Proxies   : none (direct connection)")
    log.info(f"  Output    : {ndjson_path}\n")

    seen_urls: set[str] = set()
    total_unique = 0

    for i, keyword in enumerate(KEYWORDS, start=1):
        if total_unique >= TARGET_TOTAL:
            log.info("  Target reached — stopping keyword loop.")
            break

        want = min(RESULTS_PER_BATCH, TARGET_TOTAL - total_unique)
        log.info(f"  [{i}/{len(KEYWORDS)}] '{keyword}' — requesting {want} results")

        batch_df = scrape_batch(keyword, country, want)

        if batch_df.empty:
            log.warning("    → No results — skipping")
        else:
            records = df_to_records(batch_df)

            new_records = []
            for rec in records:
                url = rec.get("job_url")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                new_records.append(rec)

            if new_records:
                append_to_ndjson(new_records, ndjson_path)
                total_unique += len(new_records)
                log.info(f"    → {len(new_records)} new | Total: {total_unique:,}")
            else:
                log.info(f"    → All {len(records)} results were duplicates")

        if i < len(KEYWORDS) and total_unique < TARGET_TOTAL:
            delay = random.randint(*DELAY_SECONDS)
            log.info(f"    Waiting {delay}s...\n")
            time.sleep(delay)

    log.info(f"\n  Done — {total_unique:,} unique jobs saved to {ndjson_path.resolve()}")
    log.info(f"  Convert:  python convert_to_excel.py {ndjson_path.name}\n")


# ── Main ───────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape LinkedIn job postings by country."
    )
    parser.add_argument(
        "--country",
        nargs="+",
        default=DEFAULT_COUNTRIES,
        metavar="COUNTRY",
        help=(
            'One or more countries to scrape. Wrap multi-word names in quotes. '
            'Examples: --country Qatar  OR  --country "Saudi Arabia" UAE Egypt'
        ),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    countries = args.country

    log.info("=" * 55)
    log.info(f"  LinkedIn Job Scraper")
    log.info(f"  Countries : {', '.join(countries)}")
    log.info(f"  Target    : {TARGET_TOTAL:,} jobs per country")
    log.info("=" * 55 + "\n")

    for idx, country in enumerate(countries, start=1):
        log.info(f"── Country {idx}/{len(countries)}: {country} ──────────────────────")
        scrape_country(country)

        # Pause between countries to avoid triggering LinkedIn's cross-session
        # rate limits (skip pause after the last country)
        if idx < len(countries):
            pause = random.randint(*DELAY_BETWEEN_COUNTRIES)
            log.info(f"Pausing {pause}s before next country...\n")
            time.sleep(pause)

    log.info("=" * 55)
    log.info(f"  All done. {len(countries)} country/countries scraped.")
    log.info("=" * 55)


if __name__ == "__main__":
    main()
