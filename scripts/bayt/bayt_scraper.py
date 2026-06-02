"""Scrape every job posting from a bayt.com country listing using proxies.

The pipeline has three stages:

1. **Listing scrape** — paginate through https://www.bayt.com/en/<country>/jobs/
   and collect one record per job tile (job_id, title, company, location, ...).
2. **Detail enrichment** — for every job, fetch its detail page through the
   same proxy pool and reduce the visible content to a single
   ``Original_Page_Content`` blob that mirrors the reference workbook.
3. **LLM extraction** — pass each blob through OpenAI (default ``gpt-5-mini``)
   to populate the 12 structured fields (category, salary, skills, ...).

Outputs are written to ``bayt_jobs_<DD_Mon_YYYY>.{json,csv,xlsx}`` so the file
name matches the convention used by ``bayt_jobs_22_Nov_2025.xlsx``.

Each worker thread is pinned to its own proxy from ``proxies.txt``. Bayt is
fronted by Cloudflare, so requests are made through ``curl_cffi`` with Chrome
TLS impersonation (a plain ``requests`` session is rejected with HTTP 403 /
``cf-mitigated: challenge``).

Usage:
    python scrape_bayt_qatar.py                                    # qatar
    python scrape_bayt_qatar.py --country saudi-arabia
    python scrape_bayt_qatar.py --country uae --workers 8
    python scrape_bayt_qatar.py --max-pages 5                      # smoke test
    python scrape_bayt_qatar.py --no-enrich                        # listing only
    python scrape_bayt_qatar.py --no-llm                           # skip OpenAI
    python scrape_bayt_qatar.py --from-json prev.json --no-enrich  # re-LLM
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import logging
import os
import queue
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

BASE_URL = "https://www.bayt.com"
DEFAULT_PROXIES_FILE = "proxies.txt"

# bayt.com country slug -> human-readable label used in output filenames.
# Slugs match the URL path segment, e.g. https://www.bayt.com/en/<slug>/jobs/.
COUNTRY_CHOICES: dict[str, str] = {
    "qatar": "Qatar",
    "saudi-arabia": "Saudi_Arabia",
    "uae": "UAE",
}

LANG_CHOICES = ("en", "ar")  # bayt.com URL prefix segments

# Mutable module-level state, set from `main()` based on `--country` and
# `--lang`. Holding this here keeps the helper signatures clean (the country
# and language are session-wide constants).
COUNTRY_SLUG = "qatar"
COUNTRY_LABEL = COUNTRY_CHOICES[COUNTRY_SLUG]
LANG = "en"
LISTING_URL = f"{BASE_URL}/{LANG}/{COUNTRY_SLUG}/jobs/"


def set_country(slug: str, lang: str = "en") -> None:
    """Switch the global country + language target (URL + filename label)."""
    global COUNTRY_SLUG, COUNTRY_LABEL, LANG, LISTING_URL
    if slug not in COUNTRY_CHOICES:
        raise ValueError(
            f"Unknown country {slug!r}; choose from {sorted(COUNTRY_CHOICES)}"
        )
    if lang not in LANG_CHOICES:
        raise ValueError(f"Unknown lang {lang!r}; choose from {LANG_CHOICES}")
    COUNTRY_SLUG = slug
    COUNTRY_LABEL = COUNTRY_CHOICES[slug]
    LANG = lang
    LISTING_URL = f"{BASE_URL}/{lang}/{slug}/jobs/"

# Browser impersonation profiles verified to bypass bayt.com's Cloudflare
# challenge. Older profiles (chrome110/116) and a few odd ones (chrome142)
# are blocked, so they're intentionally excluded.
IMPERSONATE_PROFILES = [
    "chrome",
    "chrome146",
    "chrome136",
    "chrome131",
    "chrome124",
    "chrome120",
    "safari184",
    "firefox144",
]

# Columns of bayt_jobs_22_Nov_2025.xlsx, in order. Keep this list in sync with
# `Job` and the LLM JSON schema.
XLSX_COLUMNS = [
    "Job_ID",
    "Original_Page_Content",
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
    "URL",
]

LLM_FIELDS = [
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
]

DEFAULT_OPENAI_MODEL = "gpt-5-mini"

log = logging.getLogger("bayt-scraper")


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass
class Job:
    job_id: str
    title: str
    url: str
    company: Optional[str]
    company_url: Optional[str]
    location: Optional[str]
    summary: Optional[str]
    tags: list[str] = field(default_factory=list)
    salary: Optional[str] = None
    posted: Optional[str] = None
    page: int = 0

    # populated during detail-page enrichment
    original_page_content: Optional[str] = None
    detail_url: Optional[str] = None  # canonical /en/qatar/jobs/<id>
    detail_error: Optional[str] = None

    # populated during LLM extraction (each maps 1:1 to an XLSX column)
    llm: dict[str, Optional[str]] = field(default_factory=dict)
    llm_error: Optional[str] = None


# --------------------------------------------------------------------------- #
# Proxy handling
# --------------------------------------------------------------------------- #


def load_proxies(path: Path) -> list[str]:
    """Parse `host:port:user:pass` lines into proxy URLs usable by curl_cffi."""
    proxies: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) != 4:
            log.warning("Skipping malformed proxy line: %s", line)
            continue
        host, port, user, password = parts
        proxies.append(f"http://{user}:{password}@{host}:{port}")
    if not proxies:
        raise RuntimeError(f"No proxies found in {path}")
    return proxies


class ProxyPool:
    """Thread-safe pool that hands each worker its own proxy.

    Workers can ``swap()`` a misbehaving proxy for a fresh one when a request
    fails repeatedly. Hard-dead proxies are quarantined permanently; proxies
    that just got rate-limited (403) are *cooled down* — they go back into the
    pool after a delay so the whole pool isn't burned.
    """

    def __init__(self, proxies: list[str], cooldown_seconds: float = 90.0):
        random.shuffle(proxies)
        self._available: queue.Queue[str] = queue.Queue()
        for p in proxies:
            self._available.put(p)
        self._dead: set[str] = set()
        self._lock = threading.Lock()
        self._cooldown_seconds = cooldown_seconds

    def acquire(self, timeout: float = 5.0) -> str:
        return self._available.get(timeout=timeout)

    def release(self, proxy: str) -> None:
        with self._lock:
            if proxy in self._dead:
                return
        self._available.put(proxy)

    def cooldown(self, proxy: str, seconds: Optional[float] = None) -> None:
        """Park a rate-limited proxy back in the pool after a delay."""
        delay = self._cooldown_seconds if seconds is None else seconds
        with self._lock:
            if proxy in self._dead:
                return
        log.debug("Cooling down %s for %.0fs", _redact(proxy), delay)

        def _replenish() -> None:
            time.sleep(delay)
            with self._lock:
                if proxy in self._dead:
                    return
            self._available.put(proxy)

        threading.Thread(target=_replenish, daemon=True,
                         name="proxy-cooldown").start()

    def kill(self, proxy: str) -> None:
        with self._lock:
            self._dead.add(proxy)
        log.warning("Retiring dead proxy %s (total dead: %d)",
                    _redact(proxy), len(self._dead))

    def remaining(self) -> int:
        return self._available.qsize()


def _redact(proxy_url: str) -> str:
    """Strip credentials so log lines don't leak passwords."""
    return re.sub(r"//[^@]+@", "//***@", proxy_url)


# --------------------------------------------------------------------------- #
# HTTP fetching
# --------------------------------------------------------------------------- #


class RateLimited(RuntimeError):
    """Soft failure: the proxy itself probably still works, the *peer* is
    velocity-limiting us. We cool the proxy down rather than retire it."""


class Fetcher:
    """Encapsulates a curl_cffi session pinned to a single proxy."""

    def __init__(self, proxy: str, profile: str, timeout: int = 30):
        self.proxy = proxy
        self.profile = profile
        self.timeout = timeout
        self.session = cffi_requests.Session(
            impersonate=profile,
            proxies={"http": proxy, "https": proxy},
            timeout=timeout,
        )

    def get(self, url: str, *, min_bytes: int = 5000) -> str:
        resp = self.session.get(url, allow_redirects=True)
        if resp.status_code == 403:
            raise RateLimited(f"HTTP 403 for {url}")
        if resp.status_code == 429:
            raise RateLimited(f"HTTP 429 for {url}")
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code} for {url}")
        if resp.headers.get("cf-mitigated", "").lower() == "challenge":
            raise RateLimited("Cloudflare challenge served")
        text = resp.text
        if len(text) < min_bytes:
            raise RuntimeError(f"Suspiciously small response ({len(text)} bytes)")
        return text

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# Listing-page parsing
# --------------------------------------------------------------------------- #


def discover_last_page(html: str) -> int:
    """Find the highest page number from the pagination block."""
    soup = BeautifulSoup(html, "lxml")
    last_page = 1
    pagination = soup.select_one("#pagination")
    if pagination:
        for a in pagination.select("a[href]"):
            m = re.search(r"[?&]page=(\d+)", a["href"])
            if m:
                last_page = max(last_page, int(m.group(1)))
    return last_page


def parse_jobs(html: str, page: int) -> list[Job]:
    soup = BeautifulSoup(html, "lxml")
    jobs: list[Job] = []
    for li in soup.select("li[data-js-job][data-job-id]"):
        job_id = li.get("data-job-id", "").strip()

        title_a = li.select_one("a[data-js-aid='jobID']")
        title = _clean(title_a.get_text(" ", strip=True)) if title_a else ""
        href = title_a["href"] if title_a and title_a.has_attr("href") else ""
        url = urljoin(BASE_URL, href) if href else ""

        company_a = li.select_one("div.job-company-location-wrapper a.t-bold") \
            or li.select_one("a[href*='/en/company/']")
        company = _clean(company_a.get_text(" ", strip=True)) if company_a else None
        company_url = urljoin(BASE_URL, company_a["href"]) if company_a and company_a.has_attr("href") else None

        loc_div = li.select_one("div.job-company-location-wrapper div.t-mute")
        location = _clean(loc_div.get_text(" ", strip=True)) if loc_div else None

        summary = None
        descr = li.select_one("div.jb-descr")
        if descr:
            text = descr.get_text(" ", strip=True)
            summary = _clean(re.sub(r"^Summary:\s*", "", text))

        tags = [
            _clean(dt.get_text(" ", strip=True))
            for dt in li.select("div.jb-tags dt")
            if dt.get_text(strip=True)
        ]

        salary = None
        for tag in tags:
            if re.search(r"\b(QAR|USD|AED|SAR|\$|€|£)\b", tag):
                salary = tag
                break

        posted_span = li.select_one("[data-automation-id='job-active-date']")
        posted = _clean(posted_span.get_text(" ", strip=True)) if posted_span else None

        if not job_id or not title:
            continue

        jobs.append(
            Job(
                job_id=job_id,
                title=title,
                url=url,
                company=company,
                company_url=company_url,
                location=location,
                summary=summary,
                tags=tags,
                salary=salary,
                posted=posted,
                page=page,
            )
        )
    return jobs


def _clean(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------------------- #
# Detail-page parsing
# --------------------------------------------------------------------------- #


# Phrases inside the detail page that always belong to chrome (apply buttons,
# share menus, mobile-app banner, ...) and just add noise for the LLM. We drop
# any line that exactly matches. Arabic equivalents are listed alongside the
# English ones so the parser works against /en/ and /ar/ pages alike.
_DETAIL_NOISE = {
    # English chrome
    "Easy Apply", "Save", "Complete Questionnaire",
    "Apply on company website", "Apply now",
    "Email to Friend", "Send Me Similar Jobs",
    "Print", "Report this job", "Share",
    "Email", "Messenger", "WhatsApp", "X", "Facebook",
    "Follow This Company", "Unfollow This Company",
    "Get the Bayt App", "Use Our Mobile App", "Download Now",
    "Attach a Cover Letter", "Cancel", "Okay",
    "Back to the job results",
    # Arabic chrome (mirrors of the English entries above)
    "تقديم سهل", "حفظ", "إتمام الإستبيان",
    "التقديم على موقع الشركة", "تقديم الآن",
    "أرسل إلى صديق", "تلقي وظائف مماثلة",
    "اطبع", "الإبلاغ عن هذه وظيفة", "شارك",
    "البريد الإلكتروني", "ماسنجر", "واتساب", "فيس بوك",
    "تتبع الشركة", "ازالة تتبع الشركة",
    "حمّل تطبيق بيت.كوم", "حمل تطبيق بيت.كوم",
    "استخدم تطبيقنا", "حمّل الآن", "حمل الآن",
    "أرفق خطاب مع سيرتك الذاتية", "إلغاء", "حسناً", "حسنا",
    "العودة إلى نتائج البحث", "تحميل...",
}

# Section headings (h2/h3) that are pure chrome and never carry job content.
# Listed in both languages.
_DETAIL_SECTION_HEADER_NOISE = {
    "Get the Bayt App",
    "People who viewed this job also viewed",
    "حمّل تطبيق بيت.كوم",
    "حمل تطبيق بيت.كوم",
    "الأشخاص الذين شاهدوا هذه الوظيفة شاهدوا أيضاً",
}


def _block_text(node: Any) -> str:
    """Extract visible text from a BeautifulSoup node, line per block element."""
    if node is None:
        return ""
    text = node.get_text("\n", strip=True)
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if line in _DETAIL_NOISE:
            continue
        lines.append(line)
    # Collapse consecutive duplicates (Bayt repeats labels in its mobile/desktop
    # variants of the same control).
    deduped: list[str] = []
    for line in lines:
        if deduped and deduped[-1] == line:
            continue
        deduped.append(line)
    return "\n".join(deduped)


def parse_detail_page(html: str) -> tuple[str, dict[str, str]]:
    """Reduce a detail page to ``Original_Page_Content`` + light hints.

    Returns:
        (original_page_content, hints) — hints are coarse fallbacks (title,
        company, post-date) extracted from common ``data-automation-id`` /
        ``id=`` selectors. They are mostly used as a safety net if the LLM
        misses something.
    """
    soup = BeautifulSoup(html, "lxml")

    title_node = soup.select_one("#job_title") or soup.find("h3")
    title = _clean(title_node.get_text(" ", strip=True)) if title_node else None

    posted_node = soup.select_one("[data-automation-id='job-active-date']") \
        or soup.select_one("#job-post-date")
    posted = _clean(posted_node.get_text(" ", strip=True)) if posted_node else None

    type_level = soup.select_one("[data-automation-id='id_type_level_experience']")
    type_level_text = _clean(type_level.get_text(" ", strip=True)) if type_level else None

    company_meta = soup.select_one("[data-automation-id='id_company_employees_industry']")
    company_meta_text = _clean(company_meta.get_text(" ", strip=True)) if company_meta else None

    breadcrumbs = soup.select_one("#pageBreadcrumbs")
    breadcrumb_text = _clean(breadcrumbs.get_text(" ", strip=True)) if breadcrumbs else None

    main_card = None
    for h in soup.find_all(["h2", "h3"]):
        if title and _clean(h.get_text(" ", strip=True)) == title:
            main_card = h.find_parent(["section", "article", "div"])
            break

    company_block = None
    if main_card is not None:
        for a in main_card.select("a[href*='/en/company/']"):
            company_block = a.find_parent(["div", "section"]) or a
            break

    company_line = _clean(company_block.get_text(" | ", strip=True)) if company_block else None

    # Section headings drive the body of the content blob.
    section_headers = []
    for h in soup.find_all(["h2", "h3"]):
        text = _clean(h.get_text(" ", strip=True))
        if not text:
            continue
        if text in _DETAIL_SECTION_HEADER_NOISE:
            continue
        if title and text == title:
            continue
        section_headers.append((text, h))

    parts: list[str] = []
    if title:
        parts.append(f"Job Title: {title}")
    if posted:
        parts.append(f"Post Date: {posted}")

    parts.append("")  # blank line after the small header
    parts.append("[Company Info]")
    if company_line:
        parts.append(company_line)
    if company_meta_text:
        parts.append(company_meta_text)
    if type_level_text:
        parts.append(type_level_text)

    if breadcrumb_text:
        parts.append("")
        parts.append("[Job Metadata]")
        parts.append(breadcrumb_text)

    for header, node in section_headers:
        section = node.find_parent(["section", "article", "div"]) or node.parent
        body = _block_text(section)
        if not body:
            continue
        # Strip the header from the top of the body if it leads.
        body_lines = body.splitlines()
        if body_lines and body_lines[0] == header:
            body_lines = body_lines[1:]
        body = "\n".join(body_lines).strip()
        if not body:
            continue
        # Use the actual heading as a [Section] label (matches the reference
        # workbook's style of mixed-language section markers).
        parts.append("")
        parts.append(f"[Section: {header}]")
        parts.append(body)

    blob = "\n".join(p for p in parts if p is not None).strip()

    hints = {
        "title": title or "",
        "posted": posted or "",
        "company_line": company_line or "",
        "company_meta": company_meta_text or "",
        "type_level": type_level_text or "",
    }
    return blob, hints


# --------------------------------------------------------------------------- #
# Worker (shared by listing & detail fetches)
# --------------------------------------------------------------------------- #


class PageWorker:
    """One worker per thread; owns a single proxy & curl_cffi session."""

    def __init__(self, pool: ProxyPool, max_proxy_swaps: int = 3,
                 retries_per_proxy: int = 2, polite_delay: float = 0.4):
        self.pool = pool
        self.max_proxy_swaps = max_proxy_swaps
        self.retries_per_proxy = retries_per_proxy
        self.polite_delay = polite_delay
        self._fetcher: Optional[Fetcher] = None

    def _bind_proxy(self) -> None:
        if self._fetcher is not None:
            self._fetcher.close()
        proxy = self.pool.acquire()
        profile = random.choice(IMPERSONATE_PROFILES)
        self._fetcher = Fetcher(proxy, profile)
        log.debug("Thread %s bound to proxy %s (%s)",
                  threading.current_thread().name, _redact(proxy), profile)

    def _retire(self, *, mode: str) -> None:
        """mode: 'release' (success), 'cooldown' (rate-limited), 'kill' (dead)."""
        if self._fetcher is None:
            return
        proxy = self._fetcher.proxy
        self._fetcher.close()
        self._fetcher = None
        if mode == "kill":
            self.pool.kill(proxy)
        elif mode == "cooldown":
            self.pool.cooldown(proxy)
        else:
            self.pool.release(proxy)

    def fetch(self, url: str, *, min_bytes: int = 5000) -> str:
        last_err: Optional[Exception] = None
        for _swap in range(self.max_proxy_swaps):
            if self._fetcher is None:
                try:
                    self._bind_proxy()
                except queue.Empty:
                    raise RuntimeError("Proxy pool exhausted") from None

            rate_limited_this_proxy = False
            for attempt in range(self.retries_per_proxy):
                try:
                    text = self._fetcher.get(url, min_bytes=min_bytes)
                    time.sleep(self.polite_delay)
                    return text
                except RateLimited as e:
                    last_err = e
                    rate_limited_this_proxy = True
                    log.info(
                        "url=%s via %s attempt %d/%d rate-limited: %s",
                        url, _redact(self._fetcher.proxy),
                        attempt + 1, self.retries_per_proxy, e,
                    )
                    # Back off harder than for transient errors so the peer
                    # has a chance to forget about us.
                    time.sleep(2.0 + random.random() * 2.0)
                except Exception as e:
                    last_err = e
                    log.info(
                        "url=%s via %s attempt %d/%d failed: %s",
                        url, _redact(self._fetcher.proxy),
                        attempt + 1, self.retries_per_proxy, e,
                    )
                    time.sleep(0.5 + random.random())

            self._retire(mode="cooldown" if rate_limited_this_proxy else "kill")

        raise RuntimeError(f"Failed {url} after {self.max_proxy_swaps} proxy swaps: {last_err}")

    # Convenience wrappers so call sites read clearly.
    def fetch_listing_page(self, page: int) -> str:
        return self.fetch(f"{LISTING_URL}?page={page}")

    def fetch_detail(self, url: str) -> str:
        return self.fetch(url, min_bytes=2000)

    def shutdown(self) -> None:
        self._retire(mode="release")


_thread_local = threading.local()


def _get_worker(pool: ProxyPool, polite_delay: float = 0.4) -> PageWorker:
    worker = getattr(_thread_local, "worker", None)
    if worker is None:
        worker = PageWorker(pool, polite_delay=polite_delay)
        _thread_local.worker = worker
    return worker


def _scrape_listing_page(page: int, pool: ProxyPool) -> list[Job]:
    worker = _get_worker(pool)
    html = worker.fetch_listing_page(page)
    jobs = parse_jobs(html, page)
    log.info("listing page=%d -> %d jobs", page, len(jobs))
    return jobs


def _enrich_one(job: Job, pool: ProxyPool, polite_delay: float = 1.0) -> Job:
    """Fetch the detail page for `job` and stuff Original_Page_Content."""
    worker = _get_worker(pool, polite_delay=polite_delay)
    detail_url = f"{BASE_URL}/{LANG}/{COUNTRY_SLUG}/jobs/{job.job_id}"
    job.detail_url = detail_url
    try:
        html = worker.fetch_detail(detail_url)
        blob, _hints = parse_detail_page(html)
        if not blob:
            raise RuntimeError("empty parsed detail blob")
        job.original_page_content = blob
    except Exception as e:
        job.detail_error = str(e)
        log.warning("detail fail for %s: %s", job.job_id, e)
    return job


# --------------------------------------------------------------------------- #
# LLM extraction
# --------------------------------------------------------------------------- #


_LLM_SYSTEM_PROMPT = """\
You normalize Arabic / English bayt.com job postings into a strict JSON object.

Output ONLY a single JSON object whose keys are exactly:
Job_Title, Company_Name, Job_Category, Job_Location, Salary_Range_USD,
Employment_Type, Career_Level, Years_of_Experience, Company_Size,
Job_Description, Job_Skills, Required_Qualifications, Gender, Post_Date,
Education_Level, Language_Requirement.

Rules:
- All field values are either a string or null. Never use empty arrays or
  objects. If a field cannot be confidently inferred from the text, use null.
- Translate any Arabic into clean English when populating English fields, but
  keep `Post_Date` exactly as it appears on the page (Arabic or English).
- `Job_Title` and `Company_Name` are short, title-cased strings.
- `Job_Category` is a 1-3 word industry / function name (e.g. "Tech",
  "Education", "Construction", "Sales", "Healthcare").
- `Job_Location` is "City, Qatar" if a city is given, otherwise "Qatar".
- `Salary_Range_USD` is "X-Y USD/month" or "X USD/month" if a salary is
  stated; otherwise null. Convert other currencies to USD using these rough
  rates: 1 QAR = 0.27 USD, 1 SAR = 0.27 USD, 1 AED = 0.27 USD, 1 EUR = 1.08
  USD, 1 GBP = 1.27 USD. Round to nearest 10.
- `Employment_Type` ∈ {"Full-Time","Part-Time","Contract","Internship",
  "Temporary","Freelance"} or null.
- `Career_Level` is short (e.g. "Entry-Level", "Mid-Level", "Senior",
  "Manager", "Director", "Executive") or null.
- `Years_of_Experience` is a brief phrase like "2-5 years", "10+ years",
  "Minimum 2 years" or null.
- `Company_Size` like "50-99 employees", "100-499 employees" or null.
- `Job_Description` is a concise English paragraph (≤ 1000 chars) summarizing
  the role from the description section.
- `Job_Skills` is a single string of skills separated by '; '. Each skill is
  a short English phrase. Empty -> null.
- `Required_Qualifications` is a single string of qualifications separated by
  '; '. Empty -> null.
- `Gender` ∈ {"Male","Female","Any"} or null. Only set if the post explicitly
  prefers a gender.
- `Education_Level` is the highest required degree as a short phrase (e.g.
  "Bachelor", "Master", "PhD", "Diploma", "High School") or null.
- `Language_Requirement` is a short English phrase (e.g. "Arabic fluency
  mandatory", "Excellent English communication") or null.
"""


def _build_openai_client(api_key: Optional[str]):
    from openai import OpenAI  # local import so the dep is optional
    return OpenAI(api_key=api_key) if api_key else OpenAI()


_LLM_JSON_SCHEMA = {
    "name": "BaytJobExtraction",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": LLM_FIELDS,
        "properties": {
            f: {"type": ["string", "null"]} for f in LLM_FIELDS
        },
    },
}


def llm_extract_one(client, model: str, job: Job) -> Job:
    if not job.original_page_content:
        job.llm_error = job.detail_error or "no detail content"
        return job

    user_prompt = (
        "Extract the structured fields from the following bayt.com job page. "
        "Use the listing-tile metadata only as a fallback if the detail "
        "content is missing the field.\n\n"
        f"=== Listing tile ===\n"
        f"Job ID: {job.job_id}\n"
        f"Title (listing): {job.title}\n"
        f"Company (listing): {job.company}\n"
        f"Location (listing): {job.location}\n"
        f"Salary tag (listing): {job.salary}\n"
        f"Tags (listing): {', '.join(job.tags) if job.tags else ''}\n"
        f"Posted (listing): {job.posted}\n\n"
        f"=== Detail page content ===\n"
        f"{job.original_page_content}\n"
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _LLM_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_schema", "json_schema": _LLM_JSON_SCHEMA},
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
    except Exception as e:
        job.llm_error = str(e)
        log.warning("LLM extract fail for %s: %s", job.job_id, e)
        return job

    # Coerce missing/non-string values to None so the XLSX has clean cells.
    cleaned: dict[str, Optional[str]] = {}
    for key in LLM_FIELDS:
        val = data.get(key)
        if isinstance(val, str):
            val = val.strip() or None
        elif val in (None, "", []):
            val = None
        else:
            val = str(val)
        cleaned[key] = val
    job.llm = cleaned
    return job


def run_llm_extraction(
    jobs: list[Job],
    model: str,
    workers: int,
    api_key: Optional[str],
    progress_path: Optional[Path] = None,
    checkpoint_path: Optional[Path] = None,
    checkpoint_every: int = 100,
) -> None:
    client = _build_openai_client(api_key)
    pending = [j for j in jobs if not j.llm and j.original_page_content]
    if not pending:
        log.info("LLM: no pending jobs (skipping)")
        return
    log.info("LLM: extracting %d jobs with %s using %d threads",
             len(pending), model, workers)

    progress_lock = threading.Lock()
    progress_handle = progress_path.open("a", encoding="utf-8") if progress_path else None
    try:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="llm") as ex:
            futs = {ex.submit(llm_extract_one, client, model, j): j for j in pending}
            done = 0
            try:
                for fut in as_completed(futs):
                    job = fut.result()
                    done += 1
                    if progress_handle is not None:
                        with progress_lock:
                            progress_handle.write(json.dumps(asdict(job), ensure_ascii=False) + "\n")
                            progress_handle.flush()
                    if done % 25 == 0:
                        ok = sum(1 for p in pending if p.llm)
                        log.info("LLM progress: %d / %d (ok=%d)", done, len(pending), ok)
                    if checkpoint_path is not None and done % checkpoint_every == 0:
                        write_json(jobs, checkpoint_path)
                        log.info("LLM checkpoint: saved %s", checkpoint_path)
            except KeyboardInterrupt:
                log.warning("Interrupted LLM extraction; saving partial...")
            finally:
                if checkpoint_path is not None:
                    write_json(jobs, checkpoint_path)
    finally:
        if progress_handle is not None:
            progress_handle.close()


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #


def write_json(jobs: list[Job], path: Path) -> None:
    path.write_text(
        json.dumps([asdict(j) for j in jobs], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_csv(jobs: list[Job], path: Path) -> None:
    if not jobs:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(asdict(jobs[0]).keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for job in jobs:
            row = asdict(job)
            row["tags"] = " | ".join(row.get("tags") or [])
            row["llm"] = json.dumps(row.get("llm") or {}, ensure_ascii=False)
            writer.writerow(row)


# XLSX disallows the C0 controls except TAB (\t), LF (\n), CR (\r). Anything
# in the ranges 0x00–0x08, 0x0B, 0x0C, 0x0E–0x1F triggers IllegalCharacterError
# in openpyxl, and Excel itself caps each cell at 32_767 characters.
_XLSX_ILLEGAL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
_XLSX_CELL_CHAR_LIMIT = 32_767


def _xlsx_safe(value: Any) -> Any:
    """Strip XLSX-illegal control characters and clamp to Excel's cell limit."""
    if isinstance(value, str):
        clean = _XLSX_ILLEGAL_RE.sub("", value)
        if len(clean) > _XLSX_CELL_CHAR_LIMIT:
            clean = clean[: _XLSX_CELL_CHAR_LIMIT - 3] + "..."
        return clean
    return value


def _job_to_xlsx_row(job: Job) -> list[Any]:
    """Project a Job into the 19-column reference layout."""
    llm = job.llm or {}

    canonical_url = job.detail_url or f"{BASE_URL}/{LANG}/{COUNTRY_SLUG}/jobs/{job.job_id}"

    row = {
        "Job_ID": job.job_id,
        "Original_Page_Content": job.original_page_content,
        "Job_Title": llm.get("Job_Title") or job.title,
        "Company_Name": llm.get("Company_Name") or job.company,
        "Job_Category": llm.get("Job_Category"),
        "Job_Location": llm.get("Job_Location") or job.location,
        "Salary_Range_USD": llm.get("Salary_Range_USD"),
        "Employment_Type": llm.get("Employment_Type"),
        "Career_Level": llm.get("Career_Level"),
        "Years_of_Experience": llm.get("Years_of_Experience"),
        "Company_Size": llm.get("Company_Size"),
        "Job_Description": llm.get("Job_Description") or job.summary,
        "Job_Skills": llm.get("Job_Skills"),
        "Required_Qualifications": llm.get("Required_Qualifications"),
        "Gender": llm.get("Gender"),
        "Post_Date": llm.get("Post_Date") or job.posted,
        "Education_Level": llm.get("Education_Level"),
        "Language_Requirement": llm.get("Language_Requirement"),
        "URL": canonical_url,
    }
    return [_xlsx_safe(row[col]) for col in XLSX_COLUMNS]


def write_xlsx(jobs: list[Job], path: Path) -> None:
    """Write the workbook in the layout of bayt_jobs_22_Nov_2025.xlsx."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    ws.append(XLSX_COLUMNS)
    header_font = Font(bold=True)
    for cell in ws[1]:
        cell.font = header_font

    for job in jobs:
        ws.append(_job_to_xlsx_row(job))

    # Cap obviously over-wide columns and turn on wrap for the long blobs.
    width_overrides = {
        "Original_Page_Content": 60,
        "Job_Description": 50,
        "Job_Skills": 40,
        "Required_Qualifications": 40,
        "URL": 50,
    }
    wrap_cols = {"Original_Page_Content", "Job_Description", "Job_Skills",
                 "Required_Qualifications"}
    for idx, col in enumerate(XLSX_COLUMNS, start=1):
        letter = ws.cell(row=1, column=idx).column_letter
        ws.column_dimensions[letter].width = width_overrides.get(col, 22)
        if col in wrap_cols:
            for cell in ws[letter][1:]:
                cell.alignment = Alignment(wrap_text=True, vertical="top")

    ws.freeze_panes = "A2"
    wb.save(path)


# --------------------------------------------------------------------------- #
# Resume / serialization helpers
# --------------------------------------------------------------------------- #


def jobs_from_dicts(payload: list[dict[str, Any]]) -> list[Job]:
    jobs: list[Job] = []
    fields = {f for f in Job.__dataclass_fields__}
    for item in payload:
        kw = {k: v for k, v in item.items() if k in fields}
        kw.setdefault("tags", [])
        kw.setdefault("llm", {})
        jobs.append(Job(**kw))
    return jobs


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #


def _date_stamp() -> str:
    """Return today's date as e.g. ``22_Nov_2025`` (matches the reference)."""
    return _dt.datetime.now().strftime("%d_%b_%Y")


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Tiny dotenv loader so users can keep ``OPENAI_API_KEY`` in ``.env``."""
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
        if (len(value) >= 2) and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _default_outputs(country_label: Optional[str] = None,
                     lang: Optional[str] = None) -> tuple[str, str, str]:
    """Build dated default output filenames.

    English (default): ``bayt_jobs_Qatar_22_Nov_2025.{json,csv,xlsx}``
    Arabic:            ``bayt_jobs_Qatar_AR_22_Nov_2025.{json,csv,xlsx}``
    """
    stamp = _date_stamp()
    label = country_label or COUNTRY_LABEL
    lang = lang or LANG
    suffix = "_AR" if lang == "ar" else ""
    base = f"bayt_jobs_{label}{suffix}_{stamp}"
    return f"{base}.json", f"{base}.csv", f"{base}.xlsx"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--country", default="qatar",
                   choices=sorted(COUNTRY_CHOICES.keys()),
                   help="bayt.com country to scrape (default: qatar). "
                        "Picks both the listing URL and the output filename label.")
    p.add_argument("--lang", default="en", choices=list(LANG_CHOICES),
                   help="bayt.com language (default: en). 'ar' scrapes "
                        "/ar/<country>/jobs/ and adds an _AR suffix to the "
                        "output filenames.")
    p.add_argument("--proxies", default=DEFAULT_PROXIES_FILE,
                   help="Path to proxies.txt (host:port:user:pass per line)")
    p.add_argument("--workers", type=int, default=8,
                   help="Concurrent worker threads for HTTP fetches (default: 8). "
                        "Bayt rate-limits aggressively; values >10 trigger 403 storms.")
    p.add_argument("--llm-workers", type=int, default=8,
                   help="Concurrent OpenAI threads (default: 8)")
    p.add_argument("--detail-delay", type=float, default=1.0,
                   help="Per-request delay for detail-page fetching, seconds (default: 1.0)")
    p.add_argument("--max-pages", type=int, default=None,
                   help="Cap the number of listing pages to scrape (default: all)")
    p.add_argument("--max-jobs", type=int, default=None,
                   help="Cap the number of jobs to enrich/extract (default: all)")
    p.add_argument("--from-json", default=None,
                   help="Skip the listing scrape and load jobs from this JSON file")
    p.add_argument("--no-enrich", action="store_true",
                   help="Skip detail-page enrichment (and therefore the LLM step)")
    p.add_argument("--no-llm", action="store_true",
                   help="Skip the OpenAI extraction step")
    p.add_argument("--openai-model", default=DEFAULT_OPENAI_MODEL,
                   help=f"OpenAI model to use (default: {DEFAULT_OPENAI_MODEL})")
    p.add_argument("--openai-api-key", default=None,
                   help="Override the OPENAI_API_KEY env var")
    # Output paths default to None so we can fold in the user's --country
    # selection after argument parsing.
    p.add_argument("--out", default=None,
                   help="JSON output path (default: bayt_jobs_<COUNTRY>_<DD_Mon_YYYY>.json)")
    p.add_argument("--csv", default=None,
                   help="CSV output path (default: bayt_jobs_<COUNTRY>_<DD_Mon_YYYY>.csv)")
    p.add_argument("--xlsx", default=None,
                   help="XLSX output path (default: bayt_jobs_<COUNTRY>_<DD_Mon_YYYY>.xlsx)")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Verbose (DEBUG) logging")
    return p.parse_args()


def _scrape_listings(args: argparse.Namespace, pool: ProxyPool) -> list[Job]:
    log.info("Probing first page to discover total page count...")
    bootstrap = PageWorker(pool)
    try:
        first_html = bootstrap.fetch_listing_page(1)
    finally:
        bootstrap.shutdown()
    last_page = discover_last_page(first_html)
    log.info("Discovered last page = %d", last_page)

    first_jobs = parse_jobs(first_html, 1)
    log.info("Parsed %d jobs from page 1 (bootstrap)", len(first_jobs))

    pages_to_fetch = list(range(2, last_page + 1))
    if args.max_pages is not None:
        pages_to_fetch = pages_to_fetch[: max(0, args.max_pages - 1)]
    log.info("Will fetch %d more pages with %d workers",
             len(pages_to_fetch), args.workers)

    all_jobs: list[Job] = list(first_jobs)
    seen_ids: set[str] = {j.job_id for j in all_jobs}
    failures: list[tuple[int, str]] = []

    if pages_to_fetch:
        with ThreadPoolExecutor(max_workers=args.workers, thread_name_prefix="bayt") as ex:
            futures = {ex.submit(_scrape_listing_page, page, pool): page
                       for page in pages_to_fetch}
            try:
                for fut in as_completed(futures):
                    page = futures[fut]
                    try:
                        jobs = fut.result()
                    except Exception as e:
                        log.error("page=%d ABANDONED: %s", page, e)
                        failures.append((page, str(e)))
                        continue
                    for j in jobs:
                        if j.job_id in seen_ids:
                            continue
                        seen_ids.add(j.job_id)
                        all_jobs.append(j)
            except KeyboardInterrupt:
                log.warning("Interrupted listing scrape; saving partial...")

    if failures:
        log.warning("Listing failures (%d): %s", len(failures),
                    ", ".join(str(p) for p, _ in failures))
    return all_jobs


def _enrich_jobs(jobs: list[Job], args: argparse.Namespace,
                 pool: ProxyPool, checkpoint_path: Optional[Path] = None,
                 checkpoint_every: int = 100,
                 polite_delay: float = 1.0) -> None:
    pending = [j for j in jobs if not j.original_page_content]
    if not pending:
        log.info("Enrichment: nothing pending (skipping)")
        return
    log.info("Enrichment: fetching detail pages for %d jobs with %d workers "
             "(polite_delay=%.1fs)", len(pending), args.workers, polite_delay)

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers, thread_name_prefix="detail") as ex:
        futs = {ex.submit(_enrich_one, j, pool, polite_delay): j for j in pending}
        try:
            for fut in as_completed(futs):
                _ = fut.result()
                done += 1
                if done % 50 == 0:
                    ok = sum(1 for p in pending if p.original_page_content)
                    log.info("Enrichment progress: %d / %d (ok=%d, alive proxies=%d)",
                             done, len(pending), ok, pool.remaining())
                if checkpoint_path is not None and done % checkpoint_every == 0:
                    write_json(jobs, checkpoint_path)
                    log.info("Checkpoint: saved %s", checkpoint_path)
        except KeyboardInterrupt:
            log.warning("Interrupted enrichment; saving partial...")
        finally:
            if checkpoint_path is not None:
                write_json(jobs, checkpoint_path)

    fail = sum(1 for j in pending if j.detail_error and not j.original_page_content)
    if fail:
        log.warning("Enrichment failed for %d / %d jobs", fail, len(pending))


def main() -> int:
    _load_dotenv()
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(threadName)-12s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    set_country(args.country, args.lang)
    log.info("Target: %s [%s] (%s)", COUNTRY_LABEL, LANG, LISTING_URL)

    # Resolve any --out/--csv/--xlsx paths the user did NOT pass explicitly,
    # so they pick up the just-applied country label.
    default_json, default_csv, default_xlsx = _default_outputs()
    if args.out is None:
        args.out = default_json
    if args.csv is None:
        args.csv = default_csv
    if args.xlsx is None:
        args.xlsx = default_xlsx

    proxies = load_proxies(Path(args.proxies))
    log.info("Loaded %d proxies", len(proxies))

    if args.workers > len(proxies):
        log.warning("--workers (%d) > proxies (%d); reducing to %d so each thread gets its own proxy",
                    args.workers, len(proxies), len(proxies))
        args.workers = len(proxies)

    pool = ProxyPool(proxies)

    # ---- Stage 1: listings (or load from JSON) ----
    if args.from_json:
        log.info("Loading jobs from %s (skipping listing scrape)", args.from_json)
        payload = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        all_jobs = jobs_from_dicts(payload)
    else:
        all_jobs = _scrape_listings(args, pool)

    if args.max_jobs is not None:
        all_jobs = all_jobs[: args.max_jobs]
        log.info("Capped to %d jobs (--max-jobs)", len(all_jobs))

    out_json = Path(args.out)
    out_csv = Path(args.csv)
    out_xlsx = Path(args.xlsx)

    # Save the listing-only snapshot first so we never lose the cheap data.
    write_json(all_jobs, out_json)
    write_csv(all_jobs, out_csv)
    log.info("Saved listing snapshot: %s, %s", out_json, out_csv)

    # ---- Stage 2: detail-page enrichment ----
    if not args.no_enrich:
        _enrich_jobs(
            all_jobs, args, pool,
            checkpoint_path=out_json,
            checkpoint_every=100,
            polite_delay=args.detail_delay,
        )
        write_json(all_jobs, out_json)  # checkpoint after enrichment

    # ---- Stage 3: LLM extraction ----
    if not args.no_llm:
        api_key = args.openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            log.warning("OPENAI_API_KEY is not set; skipping LLM extraction.")
        else:
            run_llm_extraction(
                all_jobs,
                model=args.openai_model,
                workers=args.llm_workers,
                api_key=api_key,
                progress_path=out_json.with_suffix(".llm.jsonl"),
                checkpoint_path=out_json,
                checkpoint_every=100,
            )
            write_json(all_jobs, out_json)  # final checkpoint

    # ---- Final write: refresh CSV + write XLSX in the reference layout ----
    write_csv(all_jobs, out_csv)
    write_xlsx(all_jobs, out_xlsx)

    log.info("Done. Total jobs: %d. Wrote %s, %s, %s",
             len(all_jobs), out_json, out_csv, out_xlsx)
    log.info("Proxies remaining alive: %d", pool.remaining())
    return 0


if __name__ == "__main__":
    sys.exit(main())
