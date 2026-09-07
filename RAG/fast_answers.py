"""Fast, deterministic answers for common labour-market questions.

This module deliberately does not call an LLM. Exact counts, rankings, trends,
scope questions, and common career guidance are calculated from the selected
rows so they are fast, repeatable, and easy to test. Questions that genuinely
need semantic document retrieval return ``None`` and continue through RAG.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

import pandas as pd

from analytics import _parse_skills, _sort_timelines_chrono
from filter_registry import FILTER_REGISTRY


COUNTRY_ALIASES = {
    "qatar": "Qatar", "doha": "Qatar", "قطر": "Qatar",
    "saudi arabia": "Saudi Arabia", "saudi": "Saudi Arabia", "ksa": "Saudi Arabia",
    "السعودية": "Saudi Arabia", "المملكة العربية السعودية": "Saudi Arabia",
    "united arab emirates": "UAE", "uae": "UAE", "emirates": "UAE",
    "الإمارات": "UAE", "الامارات": "UAE",
}

_FOLLOWUP_RE = re.compile(
    r"^(?:so|and|also|then|now|what about|how about|those|these|them|they|"
    r"as (?:a|an)|which (?:of )?those|tell me more|وماذا|ماذا عن|وهل|ثم|أيضا|أيضاً)\b",
    re.IGNORECASE,
)
_ALL_COUNTRIES_RE = re.compile(
    r"\b(each|every|all|across|by) (?:of the )?(?:three )?countries\b|"
    r"\bacross (?:qatar|the gcc|selected countries)\b|"
    r"(?:كل|جميع|بين) (?:الدول|البلدان)(?: الثلاث)?|كل دولة",
    re.IGNORECASE,
)
_DATA_ROLE_RE = re.compile(
    r"\b(?:data analyst|data scientist|data engineer|data science|business intelligence|"
    r"bi analyst|analytics analyst|strategy and data analyst)\b",
    re.IGNORECASE,
)
_AI_ROLE_RE = re.compile(
    r"\b(?:artificial intelligence|ai engineer|ai specialist|machine learning|ml engineer|"
    r"data scientist|data science|applied ai|generative ai|genai)\b",
    re.IGNORECASE,
)
_TECH_ROLE_RE = re.compile(
    r"\b(?:software|developer|programmer|technology|information technology|it |data|"
    r"cyber|cloud|network|systems? engineer|computer science|ai|machine learning)\b",
    re.IGNORECASE,
)

_EMPLOYMENT_TYPE_QUERIES = (
    ("Full-Time", re.compile(r"\bfull[ -]?time\b|دوام كامل", re.IGNORECASE)),
    ("Part-Time", re.compile(r"\bpart[ -]?time\b|دوام جزئي", re.IGNORECASE)),
    ("Contract", re.compile(r"\bcontract(?:ual)?\b|تعاقد|بعقد|عقود", re.IGNORECASE)),
    ("Internship", re.compile(r"\bintern(?:ship)?s?\b|تدريب|متدرب", re.IGNORECASE)),
    ("Freelance", re.compile(r"\bfreelanc(?:e|er|ing)\b|عمل حر|مستقل", re.IGNORECASE)),
    ("Temporary", re.compile(r"\btemporar(?:y|ily)\b|مؤقت", re.IGNORECASE)),
    ("Remote", re.compile(r"\bremote\b|عن بعد", re.IGNORECASE)),
    ("Volunteer", re.compile(r"\bvolunteer(?:s|ing)?\b|تطوع", re.IGNORECASE)),
)

_ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
_ARABIC_COUNTRIES = {"Qatar": "قطر", "Saudi Arabia": "السعودية", "UAE": "الإمارات"}
_ARABIC_TIMELINES = {"May 2026": "مايو 2026", "Jun 2026": "يونيو 2026"}


def _is_arabic(text: str) -> bool:
    return bool(_ARABIC_RE.search(text or ""))


def _display_country(country: str, arabic: bool) -> str:
    return _ARABIC_COUNTRIES.get(country, country) if arabic else country


def _display_timeline(timeline: str, arabic: bool) -> str:
    return _ARABIC_TIMELINES.get(timeline, timeline) if arabic else timeline


def _localized_scope(countries: list[str], timelines: list[str], count: int, arabic: bool) -> str:
    if arabic:
        country_label = "، ".join(_display_country(v, True) for v in countries) or "الدول المحددة"
        time_label = "–".join(_display_timeline(v, True) for v in timelines) or "الفترة المتاحة"
        return f"{country_label} · {time_label} · {count:,} إعلان وظيفي"
    country_label = ", ".join(countries) if countries else "selected countries"
    time_label = "–".join(timelines) if timelines else "available period"
    return f"{country_label} · {time_label} · {count:,} postings"


def _source_caveat(scoped: pd.DataFrame, arabic: bool) -> str:
    """Explain snapshot-source changes whenever a time comparison mixes sources."""
    if "_timeline" not in scoped.columns or "_source" not in scoped.columns:
        return ""
    pairs = scoped[["_timeline", "_source"]].dropna().drop_duplicates()
    if len(pairs["_timeline"].unique()) < 2 or len(pairs["_source"].unique()) < 2:
        return ""
    if arabic:
        return (
            "**ملاحظة منهجية:** بيانات مايو مأخوذة من Bayt وبيانات يونيو من LinkedIn؛ "
            "لذلك يصف التغير اختلاف لقطتي البيانات ولا يثبت وحده تغير السوق الفعلي."
        )
    return (
        "**Method note:** May data comes from Bayt and June data comes from LinkedIn. "
        "The change describes these two dataset snapshots and does not, by itself, prove a market-wide change."
    )

_SKILL_ALIASES = {
    "communication skill": "Communication",
    "communication skills": "Communication",
    "communication": "Communication",
    "project management": "Project Management",
    "data analysis": "Data Analysis",
    "data analytics": "Data Analysis",
    "machine learning": "Machine Learning",
    "problem solving": "Problem Solving",
    "problem-solving": "Problem Solving",
    "analytical skill": "Analytical Skills",
    "analytical skills": "Analytical Skills",
    "team collaboration": "Collaboration",
    "collaboration": "Collaboration",
    "teamwork": "Teamwork",
    "power bi": "Power BI",
    "sql server": "SQL Server",
    "microsoft excel": "Excel",
    "ms excel": "Excel",
    "python": "Python",
    "sql": "SQL",
    "oracle": "Oracle",
}

_TECHNICAL_SKILLS = {
    "Python", "SQL", "SQL Server", "Power BI", "Excel", "Machine Learning",
    "Data Analysis", "Data Visualization", "Oracle", "Cloud Computing", "AWS",
    "Azure", "Git", "Docker", "TensorFlow", "PyTorch", "Statistics", "Tableau",
    "Natural Language Processing", "NLP", "Deep Learning", "Java", "JavaScript",
    "Network Security", "Cybersecurity", "Information Security", "Penetration Testing",
    "Linux", "Firewalls", "SIEM", "Incident Response", "Risk Management",
}
_SOFT_SKILLS = {
    "Communication", "Leadership", "Problem Solving", "Collaboration", "Teamwork",
    "Attention To Detail", "Time Management", "Critical Thinking", "Negotiation",
    "Organizational Skills", "Stakeholder Management",
}

# Keep this deliberately small and explicit.  These are programming languages,
# not the wider set of technical tools which can also appear in ``skills``.
_PROGRAMMING_LANGUAGES = {
    "Python", "SQL", "Java", "JavaScript", "TypeScript", "C++", "C#", "C",
    "R", "PHP", "Ruby", "Go", "Scala", "Kotlin", "Swift", "MATLAB",
}
_QUERY_SKILLS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Python", re.compile(r"\bpython\b", re.I)),
    ("SQL", re.compile(r"\bsql\b", re.I)),
    ("Power BI", re.compile(r"\bpower\s*bi\b", re.I)),
    ("Excel", re.compile(r"\b(?:microsoft |ms )?excel\b", re.I)),
    ("JavaScript", re.compile(r"\bjavascript\b", re.I)),
    ("TypeScript", re.compile(r"\btypescript\b", re.I)),
    ("Java", re.compile(r"\bjava\b", re.I)),
    ("C++", re.compile(r"\bc\+\+\b", re.I)),
    ("C#", re.compile(r"\bc#\b", re.I)),
    ("R", re.compile(r"\bR language\b", re.I)),
)


def _mentioned_skills(text: str) -> list[str]:
    """Return explicitly named skills in prompt order, without duplicates."""
    found: list[str] = []
    for name, pattern in _QUERY_SKILLS:
        if pattern.search(text) and name not in found:
            found.append(name)
    return found


def canonical_skill(value: str) -> str:
    """Return one display label for capitalization and common wording variants."""
    cleaned = re.sub(r"\s+", " ", str(value or "").strip())
    key = cleaned.casefold().rstrip(".")
    if key in _SKILL_ALIASES:
        return _SKILL_ALIASES[key]
    if not cleaned:
        return ""
    if cleaned.isupper() and len(cleaned) <= 6:
        return cleaned
    return cleaned.title()


def _skills_by_posting(df: pd.DataFrame) -> Counter:
    counts: Counter = Counter()
    if "skills" not in df.columns:
        return counts
    for raw in df["skills"].dropna():
        skills = {canonical_skill(skill) for skill in _parse_skills(raw)}
        counts.update(skill for skill in skills if skill)
    return counts


def _scope_base(
    df: pd.DataFrame,
    dump_ids: list[str] | None,
    explicit_filters: dict[str, str] | None = None,
) -> pd.DataFrame:
    scoped = df
    if dump_ids and "_dump_id" in scoped.columns:
        scoped = scoped[scoped["_dump_id"].isin(dump_ids)]
    for key, raw_value in (explicit_filters or {}).items():
        field = FILTER_REGISTRY.get(key)
        if field is None or field.column not in scoped.columns:
            continue
        value = field.normalize(raw_value) if field.normalize else str(raw_value).strip()
        if value is None or not str(value).strip():
            continue
        scoped = scoped[
            scoped[field.column].fillna("").astype(str).str.casefold().eq(str(value).casefold())
        ]
    # Read-only views are sufficient. Copying every wide text column (including
    # descriptions) added seconds to otherwise tiny calculations.
    return scoped


def _mentioned_countries(text: str) -> list[str]:
    lowered = text.casefold()
    found: list[str] = []
    for alias, country in sorted(COUNTRY_ALIASES.items(), key=lambda item: -len(item[0])):
        if alias.casefold() in lowered and country not in found:
            found.append(country)
    return found


def _previous_user_text(history: list[dict] | None) -> str:
    for message in reversed(history or []):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""


def _country_context(history: list[dict] | None) -> list[str]:
    """Find the most recent explicit country scope, not merely the last turn."""
    for message in reversed(history or []):
        if message.get("role") != "user":
            continue
        text = str(message.get("content", ""))
        if _ALL_COUNTRIES_RE.search(text):
            return []
        countries = _mentioned_countries(text)
        if countries:
            return countries
    return []


def _scope_question(
    base: pd.DataFrame, question: str, history: list[dict] | None,
) -> tuple[pd.DataFrame, list[str], list[str], str]:
    countries = _mentioned_countries(question)
    if not countries and _FOLLOWUP_RE.search(question) and not _ALL_COUNTRIES_RE.search(question):
        countries = _country_context(history)
    if countries and not _ALL_COUNTRIES_RE.search(question) and "_country" in base.columns:
        scoped = base[base["_country"].isin(countries)]
    else:
        scoped = base

    timelines: list[str] = []
    if "_timeline" in base.columns:
        for timeline in base["_timeline"].dropna().unique():
            if str(timeline).casefold() in question.casefold():
                timelines.append(str(timeline))
        if timelines:
            scoped = scoped[scoped["_timeline"].isin(timelines)]
        else:
            timelines = _sort_timelines_chrono([str(v) for v in scoped["_timeline"].dropna().unique()])

    visible_countries = sorted(str(v) for v in scoped.get("_country", pd.Series(dtype=str)).dropna().unique())
    country_label = ", ".join(visible_countries) if visible_countries else "selected countries"
    time_label = "–".join(timelines) if timelines else "available period"
    scope = f"{country_label} · {time_label} · {len(scoped):,} postings"
    return scoped, visible_countries, timelines, scope


def _role_scope(df: pd.DataFrame, question: str, history: list[dict] | None) -> tuple[pd.DataFrame, str]:
    text = question
    if _FOLLOWUP_RE.search(question):
        text += " " + _previous_user_text(history)
    titles = df.get("job_title", pd.Series("", index=df.index)).fillna("").astype(str)
    arabic = _is_arabic(text)
    if re.search(r"\bdata analysts?\b|محلل(?:ي|و)? البيانات|محلل بيانات", text, re.I) and not re.search(r"\bdata scientists?\b|عالم بيانات|علماء البيانات", text, re.I):
        label = "وظائف محللي البيانات" if arabic else "data analyst roles"
        return df[titles.str.contains(r"\bdata analyst\b", case=False, regex=True, na=False)], label
    if re.search(r"\bdata scientists?\b|عالم بيانات|علماء البيانات", text, re.I) and not re.search(r"\bdata analysts?\b|محلل(?:ي|و)? البيانات|محلل بيانات", text, re.I):
        label = "وظائف علماء البيانات" if arabic else "data scientist roles"
        return df[titles.str.contains(r"\bdata scientist|data science\b", case=False, regex=True, na=False)], label
    if re.search(r"\b(data roles?|data-related|data related|data analyst|data scientist)\b|وظائف البيانات|مجال البيانات|تحليل البيانات", text, re.I):
        return df[titles.str.contains(_DATA_ROLE_RE, na=False)], "وظائف البيانات" if arabic else "data roles"
    if re.search(r"\b(ai|artificial intelligence|machine learning)\b|الذكاء الاصطناعي|تعلم الآلة|التعلم الآلي", text, re.I):
        return df[titles.str.contains(_AI_ROLE_RE, na=False)], "وظائف الذكاء الاصطناعي وتعلم الآلة" if arabic else "AI and machine-learning roles"
    if re.search(r"\b(?:cybersecurity|cyber security|information security|security analyst|security engineer|soc analyst)\b|الأمن السيبراني|الأمن المعلوماتي", text, re.I):
        mask = titles.str.contains(r"cyber\s*security|information security|security (?:analyst|engineer)|soc analyst", case=False, regex=True, na=False)
        return df[mask], "وظائف الأمن السيبراني" if arabic else "cybersecurity roles"
    if re.search(r"\b(?:software engineering|software engineer|software development|software developer|programming roles?)\b|هندسة البرمجيات|تطوير البرمجيات|مبرمج", text, re.I):
        mask = titles.str.contains(r"software (?:engineer|developer)|programmer", case=False, regex=True, na=False)
        return df[mask], "وظائف هندسة البرمجيات" if arabic else "software engineering roles"
    if re.search(r"\bengineering jobs?\b|\bengineer(?:ing|s)? roles?\b|وظائف هندس|مهندس", text, re.I):
        sector = df.get("_sector_norm", pd.Series("", index=df.index)).fillna("").astype(str)
        mask = titles.str.contains(r"\bengineer(?:ing)?\b", case=False, regex=True, na=False) | sector.str.contains(
            r"engineering", case=False, regex=True, na=False,
        )
        return df[mask], "الوظائف الهندسية" if arabic else "engineering roles"
    if re.search(r"\b(technology|tech|computer science|software)\b|تقنية|تكنولوجيا|علوم الحاسوب|برمجيات", text, re.I):
        sector = df.get("_sector_norm", pd.Series("", index=df.index)).fillna("").astype(str)
        mask = titles.str.contains(_TECH_ROLE_RE, na=False) | sector.str.contains(r"technology|engineering", case=False, na=False)
        return df[mask], "الوظائف التقنية" if arabic else "technology roles"
    if re.search(r"\b(graduate|entry.level|early career|intern|trainee)\b|خريج|حديث التخرج|مبتدئ|متدرب", text, re.I):
        career = df.get("_career_norm", pd.Series("", index=df.index)).fillna("").astype(str)
        mask = career.eq("Entry-Level") | titles.str.contains(r"graduate|intern|trainee|early career|junior", case=False, regex=True, na=False)
        return df[mask], "وظائف الخريجين والمستوى المبتدئ" if arabic else "graduate and entry-level roles"
    if re.search(r"\b(senior|lead|manager|director|executive)\b|للوظائف العليا|الوظائف العليا|وظائف عليا|وظائف قيادية|كبار|مدير", text, re.I):
        career = df.get("_career_norm", pd.Series("", index=df.index)).fillna("").astype(str)
        mask = career.isin(["Senior-Level", "Management", "Executive"]) | titles.str.contains(
            r"senior|lead|manager|director|head|chief|vice president", case=False, regex=True, na=False,
        )
        return df[mask], "الوظائف العليا والقيادية" if arabic else "senior and leadership roles"
    return df, "جميع الوظائف" if arabic else "all roles"


def _job_evidence(df: pd.DataFrame, limit: int = 6) -> list[dict[str, Any]]:
    fields = ["job_title", "company", "_country", "_timeline", "category", "url"]
    evidence = []
    for _, row in df.head(limit).iterrows():
        evidence.append({
            "title": str(row.get("job_title") or "Untitled role"),
            "company": str(row.get("company") or "Company not listed"),
            "country": str(row.get("_country") or ""),
            "timeline": str(row.get("_timeline") or ""),
            "sector": str(row.get("_sector_norm") or row.get("category") or ""),
            "url": str(row.get("url") or ""),
        })
    return evidence


def _result(answer: str, intent: str, scope: str, scoped: pd.DataFrame, evidence: list[dict] | None = None) -> dict:
    return {
        "answer": answer.strip(),
        "intent": intent,
        "scope": scope,
        "evidence_count": len(scoped),
        "evidence": evidence or [],
    }


def _top_skill_rows(df: pd.DataFrame, limit: int = 8) -> list[tuple[str, int, float]]:
    total = max(len(df), 1)
    return [(skill, count, round(count * 100 / total, 1)) for skill, count in _skills_by_posting(df).most_common(limit)]


def _requested_employment_type(question: str) -> str | None:
    for label, pattern in _EMPLOYMENT_TYPE_QUERIES:
        if pattern.search(question):
            return label
    return None


def _requested_group_dimension(question: str) -> tuple[str, str, str, str] | None:
    if re.search(r"\bsectors?\b|\bindustr(?:y|ies)\b|قطاع|قطاعات|صناعة|صناعات", question, re.IGNORECASE):
        return "_sector_norm", "Sector", "القطاع", "sector"
    if re.search(r"\bcountr(?:y|ies)\b|\bnations?\b|دولة|دول|بلد|بلدان", question, re.IGNORECASE):
        return "_country", "Country", "الدولة", "country"
    if re.search(r"\bsources?\b|\bby platform\b|\bbayt\b|\blinkedin\b|مصدر|منصة", question, re.IGNORECASE):
        return "_source", "Source", "المصدر", "source"
    return None


def _employment_by_group_answer(
    scoped: pd.DataFrame,
    employment_type: str,
    scope: str,
    arabic: bool,
    group: tuple[str, str, str, str],
) -> dict | None:
    group_col, group_label, arabic_group_label, intent_suffix = group
    group_plural = "Countries" if group_label == "Country" else f"{group_label}s"
    if group_col == "_sector_norm" and group_col not in scoped.columns and "category" in scoped.columns:
        group_col = "category"
    if group_col not in scoped.columns or "_employment_norm" not in scoped.columns:
        return None

    usable = scoped[
        scoped[group_col].notna()
        & scoped[group_col].astype(str).str.strip().ne("")
    ]
    if usable.empty:
        return None

    employment = usable["_employment_norm"].fillna("").astype(str)
    matching = usable[employment.str.casefold().eq(employment_type.casefold())]
    totals = usable.groupby(group_col).size()
    matching_counts = matching.groupby(group_col).size()
    minimum_group_size = 20 if len(usable) >= 1_000 else 2
    eligible_groups = totals[totals >= minimum_group_size].index
    matching_counts = matching_counts[matching_counts.index.isin(eligible_groups)]
    rows = [
        (str(group_value), int(count), int(totals[group_value]), count * 100 / totals[group_value])
        for group_value, count in matching_counts.items()
    ]
    rows.sort(key=lambda row: (-row[3], -row[1], row[0]))

    if arabic:
        lines = [
            f"## اعتماد الفئات على وظائف {employment_type}",
            "",
            "يُرتب الجدول الفئات حسب حصة هذا النوع من التوظيف داخل كل فئة، وليس حسب الحجم الخام وحده.",
            f"تُعرض فقط الفئات التي تحتوي على {minimum_group_size:,} إعلانًا على الأقل لتجنب النسب المضللة من العينات الصغيرة.",
            "",
            f"| {arabic_group_label} | إعلانات النوع | جميع إعلانات الفئة | الحصة |",
            "|---|---:|---:|---:|",
        ]
    else:
        lines = [
            f"## {group_plural} relying most on {employment_type.lower()} employment",
            "",
            f"{group_plural} are ranked by this employment type's share within each {group_label.lower()}, not by raw posting volume alone.",
            f"Only groups with at least {minimum_group_size:,} postings are shown to avoid misleading rates from tiny samples.",
            "",
            f"| {group_label} | Matching postings | All {group_label.lower()} postings | Share |",
            "|---|---:|---:|---:|",
        ]
    lines += [f"| {group_value} | {count:,} | {total:,} | {share:.1f}% |" for group_value, count, total, share in rows[:10]]
    if not rows:
        lines += [
            "",
            (
                "لا توجد فئات تحقق الحد الأدنى لحجم العينة في النطاق المحدد."
                if arabic
                else "No groups meet the minimum base size in the selected scope."
            ),
        ]
    lines += ["", f"*النطاق: {scope}*" if arabic else f"*Scope: {scope}*"]
    return _result(
        "\n".join(lines),
        f"employment-by-{intent_suffix}",
        scope,
        matching,
        _job_evidence(matching),
    )


def _source_comparison_answer(
    scoped: pd.DataFrame,
    question: str,
    history: list[dict] | None,
    scope: str,
    arabic: bool,
) -> dict | None:
    if "_source" not in scoped.columns:
        return None
    roles, role_label = _role_scope(scoped, question, history)
    sources = roles["_source"].dropna().replace("", pd.NA).value_counts()
    if sources.empty:
        return None

    if arabic:
        lines = [
            f"## مقارنة المصادر في {role_label}",
            "",
            f"تعتمد المقارنة على **{len(roles):,} إعلانًا مطابقًا**.",
            "",
            "| المصدر | الإعلانات | الحصة | نوع التوظيف الأبرز | المستوى الوظيفي الأبرز |",
            "|---|---:|---:|---|---|",
        ]
    else:
        lines = [
            f"## Bayt versus LinkedIn for {role_label}",
            "",
            f"The comparison uses **{len(roles):,} matching postings**.",
            "",
            "| Source | Postings | Share | Leading employment type | Leading career level |",
            "|---|---:|---:|---|---|",
        ]

    for source, count in sources.items():
        source_rows = roles[roles["_source"] == source]
        employment = source_rows.get("_employment_norm", pd.Series(dtype=str)).dropna().replace("", pd.NA).value_counts()
        career = source_rows.get("_career_norm", pd.Series(dtype=str)).dropna().replace("", pd.NA).value_counts()
        leading_employment = str(employment.index[0]) if not employment.empty else "Not available"
        leading_career = str(career.index[0]) if not career.empty else "Not available"
        lines.append(
            f"| {source} | {int(count):,} | {count * 100 / max(len(roles), 1):.1f}% | "
            f"{leading_employment} | {leading_career} |"
        )

    caveat = _source_caveat(roles, arabic)
    if caveat:
        lines += ["", caveat]
    lines += ["", f"*النطاق: {scope}*" if arabic else f"*Scope: {scope}*"]
    return _result(
        "\n".join(lines),
        "source-comparison",
        scope,
        roles,
        _job_evidence(roles),
    )


def _skills_answer(scoped: pd.DataFrame, question: str, history: list[dict] | None, scope: str) -> dict:
    roles, role_label = _role_scope(scoped, question, history)
    q = question.casefold()
    arabic = _is_arabic(question)
    graduate = bool(re.search(r"graduate|entry.level|beginner|should i learn|must i have|roadmap|خريج|حديث التخرج", q))
    named_skills = _mentioned_skills(question)

    # A comparison that explicitly names skills must compare those skills, not
    # fall through to the generic country-volume comparison below.
    if named_skills and re.search(r"\b(?:compare|comparison|across|by country|each country)\b|قارن|مقارنة|بين الدول", q) and "_country" in roles.columns:
        country_order = sorted(str(value) for value in roles["_country"].dropna().unique())
        counters = {country: _skills_by_posting(group) for country, group in roles.groupby("_country")}
        lines = [
            f"## Demand for named skills in {role_label}", "",
            "Counts show postings that mention each requested skill; one posting can mention more than one skill.", "",
            "| Skill | " + " | ".join(country_order) + " | Total |",
            "|---|" + "|".join("---:" for _ in country_order) + "|---:|",
        ]
        for skill in named_skills:
            values = [counters.get(country, Counter()).get(skill, 0) for country in country_order]
            lines.append(f"| {skill} | " + " | ".join(f"{value:,}" for value in values) + f" | {sum(values):,} |")
        lines += ["", f"*Scope: {scope}*"]
        return _result("\n".join(lines), "named-skill-comparison", scope, roles, _job_evidence(roles))

    if re.search(r"\b(?:programming languages?|coding languages?)\b|لغات البرمجة", q):
        language_rows = [row for row in _top_skill_rows(roles, 80) if row[0] in _PROGRAMMING_LANGUAGES]
        lines = ([f"## أكثر لغات البرمجة ورودًا في {role_label}", "", f"استنادًا إلى **{len(roles):,} إعلانًا مطابقًا**:", ""]
                 if arabic else
                 [f"## Most requested programming languages in {role_label}", "", f"Based on **{len(roles):,} matching postings**:", ""])
        if language_rows:
            for index, (skill, count, pct) in enumerate(language_rows[:10], 1):
                lines.append(f"{index}. **{skill}** — {count:,} postings ({pct}%)")
        else:
            lines.append("No programming-language mentions were found in the selected role scope.")
        lines += ["", f"*Scope: {scope}*"]
        return _result("\n".join(lines), "programming-language-ranking", scope, roles, _job_evidence(roles))

    if re.search(r"common across|all three countries|each country|مشتركة بين|جميع الدول|كل دولة", q) and "_country" in scoped.columns:
        per_country = {
            str(country): _skills_by_posting(group)
            for country, group in scoped.groupby("_country")
        }
        common = set.intersection(*(set(counter) for counter in per_country.values())) if per_country else set()
        ranked = sorted(
            ((skill, sum(counter.get(skill, 0) for counter in per_country.values())) for skill in common),
            key=lambda item: (-item[1], item[0]),
        )[:10]
        lines = (["## المهارات المشتركة بين جميع الدول المحددة", "", "| المهارة | مرات الظهور في الإعلانات |", "|---|---:|"]
                 if arabic else
                 ["## Skills common across all selected countries", "", "| Skill | Total posting mentions |", "|---|---:|"])
        lines += [f"| {skill} | {count:,} |" for skill, count in ranked]
        note = ("تظهر المهارة هنا فقط إذا ذُكرت في إعلان واحد على الأقل في كل دولة محددة."
                if arabic else
                "A skill is included only when at least one posting mentions it in every selected country.")
        lines += ["", note, "", f"*النطاق: {scope}*" if arabic else f"*Scope: {scope}*"]
        return _result("\n".join(lines), "cross-country-skills", scope, scoped)

    analyst_mentioned = "data analyst" in q or "محلل بيانات" in q or "محللي البيانات" in q
    scientist_mentioned = "data scientist" in q or "عالم بيانات" in q or "علماء البيانات" in q
    if analyst_mentioned and scientist_mentioned:
        titles = scoped.get("job_title", pd.Series("", index=scoped.index)).fillna("").astype(str)
        analyst = scoped[titles.str.contains(r"\bdata analyst\b", case=False, regex=True, na=False)]
        scientist = scoped[titles.str.contains(r"\bdata scientist|data science\b", case=False, regex=True, na=False)]
        left, right = _top_skill_rows(analyst, 6), _top_skill_rows(scientist, 6)
        lines = (["## مهارات محلل البيانات مقابل عالم البيانات", "", "| محلل البيانات | عالم البيانات |", "|---|---|"]
                 if arabic else
                 ["## Data analyst vs. data scientist skills", "", "| Data analyst | Data scientist |", "|---|---|"])
        for i in range(max(len(left), len(right))):
            a = f"{left[i][0]} ({left[i][1]})" if i < len(left) else "—"
            s = f"{right[i][0]} ({right[i][1]})" if i < len(right) else "—"
            lines.append(f"| {a} | {s} |")
        evidence_line = (f"*الدليل: {len(analyst):,} إعلانًا لمحللي البيانات و{len(scientist):,} إعلانًا لعلماء البيانات · {scope}*"
                         if arabic else
                         f"*Evidence: {len(analyst):,} analyst and {len(scientist):,} scientist postings · {scope}*")
        lines += ["", evidence_line]
        return _result("\n".join(lines), "skills-comparison", scope, pd.concat([analyst, scientist]), _job_evidence(pd.concat([analyst, scientist])))

    rows = _top_skill_rows(roles, 12)
    if graduate:
        technical = [row for row in rows if row[0] in _TECHNICAL_SKILLS]
        soft = [row for row in rows if row[0] in _SOFT_SKILLS]
        if len(technical) < 5:
            technical = [row for row in _top_skill_rows(roles, 40) if row[0] in _TECHNICAL_SKILLS][:6]
        # New/emerging role families (notably cybersecurity) can contain
        # legitimate tools absent from the compact allowlist above.  Never
        # render an empty recommendation section: use the role's most common
        # non-soft skills as an evidence-backed fallback.
        if not technical:
            technical = [row for row in _top_skill_rows(roles, 40) if row[0] not in _SOFT_SKILLS][:6]
        lines = (["## المهارات التي تستحق الأولوية", "",
                  f"إذا كنت حديث التخرج وتستهدف **{role_label}**، فابدأ بهذه المهارات المدعومة ببيانات الإعلانات:", ""]
                 if arabic else
                 ["## Skills to prioritize", "",
                  f"For a recent graduate targeting **{role_label}**, start with these evidence-backed skills:", ""])
        for i, (skill, count, pct) in enumerate(technical[:6], 1):
            lines.append((f"{i}. **{skill}** — ذُكرت في {count:,} إعلانًا مطابقًا ({pct}%)."
                          if arabic else
                          f"{i}. **{skill}** — mentioned in {count:,} matching postings ({pct}%)."))
        if soft:
            heading = "### المهارات المهنية" if arabic else "### Professional skills"
            separator = "، " if arabic else ", "
            lines += ["", heading, "", separator.join(f"**{name}**" for name, _, _ in soft[:4]) + "."]
        if arabic:
            lines += ["", "### الخطوة العملية التالية", "",
                      "أنشئ مشروعًا واحدًا في ملف أعمالك يجمع أول ثلاث مهارات تقنية، ووثّقه بوضوح، ثم عدّل سيرتك الذاتية لتستخدم المصطلحات الواردة في الإعلانات المطابقة.",
                      "", f"*استنادًا إلى {len(roles):,} إعلانًا مطابقًا · {scope}*"]
        else:
            lines += ["", "### Practical next step", "",
                      "Build one portfolio project that combines the first three technical skills, document it clearly, and tailor your CV to the wording used in matching vacancies.",
                      "", f"*Based on {len(roles):,} matching postings · {scope}*"]
        return _result("\n".join(lines), "career-guidance", scope, roles, _job_evidence(roles))

    lines = ([f"## أكثر المهارات طلبًا في {role_label}", "", f"استنادًا إلى **{len(roles):,} إعلانًا مطابقًا**:", ""]
             if arabic else
             [f"## Most requested skills in {role_label}", "", f"Based on **{len(roles):,} matching postings**:", ""])
    for i, (skill, count, pct) in enumerate(rows[:10], 1):
        lines.append((f"{i}. **{skill}** — {count:,} إعلانًا ({pct}%)" if arabic else f"{i}. **{skill}** — {count:,} postings ({pct}%)"))
    lines += ["", f"*النطاق: {scope}*" if arabic else f"*Scope: {scope}*"]
    return _result("\n".join(lines), "skills-ranking", scope, roles, _job_evidence(roles))


def build_fast_answer(
    df: pd.DataFrame,
    question: str,
    history: list[dict] | None = None,
    dump_ids: list[str] | None = None,
    explicit_filters: dict[str, str] | None = None,
) -> dict | None:
    """Return a deterministic response, or ``None`` when full RAG is needed."""
    clean = re.sub(r"^[-*]\s*", "", str(question or "").strip())
    q = clean.casefold()
    arabic = _is_arabic(clean)

    # Conversation/help messages must be instant. They do not depend on the
    # selected dataframe, so avoid paying for country/timeline scans before
    # recognizing them—especially while another semantic request is using CPU.
    if re.fullmatch(r"(?:hi|hello|hey|hey there|مرحبا|مرحباً|السلام عليكم)[!?. ]*", q):
        answer = ("مرحبًا! اسألني عن أعداد الوظائف أو المهارات أو الرواتب أو أصحاب العمل أو القطاعات أو تغيرات التوظيف في قطر والسعودية والإمارات."
                  if arabic else
                  "Hello! Ask me about job counts, skills, salaries, employers, sectors, or hiring changes across Qatar, Saudi Arabia, and the UAE.")
        return _result(answer, "conversation", "", df.iloc[:0])
    if re.search(r"\bwho are you\b|\bwhat can you do\b|how should i use|كيف أستخدم|ماذا يمكنك", q):
        answer = ("أنا **مِهنة**، مساعد بحثي لسوق العمل الخليجي. أحلل مجموعات بيانات إعلانات الوظائف المحددة للإجابة عن حجم التوظيف والمهارات وأصحاب العمل والرواتب والقطاعات والتغير عبر الزمن. للحصول على أدق نتيجة، اذكر وظيفة أو دولة أو فترة، أو اطلب مقارنة بينها."
                  if arabic else
                  "I’m **Mihna**, a GCC labour-market research assistant. I analyse the selected job-posting datasets to answer questions about hiring volume, skills, employers, salaries, sectors, and changes over time. For the clearest result, name a role, country, or period—or ask me to compare them.")
        return _result(answer, "help", "", df.iloc[:0])

    base = _scope_base(df, dump_ids, explicit_filters)
    scoped, countries, timelines, scope = _scope_question(base, clean, history)
    scope = _localized_scope(countries, timelines, len(scoped), arabic)

    # Out-of-scope years and domains receive an immediate, honest response.
    requested_years = {int(year) for year in re.findall(r"\b(?:19|20)\d{2}\b", clean)}
    available_years = {
        int(year) for value in base.get("_timeline", pd.Series(dtype=str)).dropna()
        for year in re.findall(r"\b(?:19|20)\d{2}\b", str(value))
    }
    if requested_years and not requested_years.issubset(available_years):
        answer = (
            "## لا توجد بيانات لهذه الفترة\n\n"
            f"تغطي البيانات المحددة **مايو ويونيو 2026 فقط**، لذلك لا أستطيع تقديم إجابة موثوقة عن {'، '.join(str(v) for v in sorted(requested_years))}. "
            "اختر فترة متاحة أو أضف مجموعة بيانات جديدة أولًا."
            if arabic else
            "## No data for that period\n\n"
            f"The selected data covers **May and June 2026 only**, so I cannot give a reliable answer for {', '.join(str(v) for v in sorted(requested_years))}. "
            "Choose an available period or add a new dataset first."
        )
        return _result(answer, "out-of-scope", scope, scoped)

    if re.search(r"\b(?:weather|temperature|sports?|recipe|mars)\b|الطقس|درجة الحرارة|رياضة|وصفة|المريخ", q):
        answer = (
            "## خارج نطاق البيانات\n\nأستطيع الإجابة فقط عن سوق العمل في قطر والسعودية والإمارات باستخدام بيانات الوظائف المحددة."
            if arabic else
            "## Outside the dataset scope\n\nI can answer only about the Qatar, Saudi Arabia, and UAE labour markets using the selected job-posting data."
        )
        return _result(answer, "out-of-scope", scope, scoped)

    if "what countries" in q or "countries does" in q or "الدول" in q and "تغطي" in q:
        names = sorted(str(v) for v in base.get("_country", pd.Series(dtype=str)).dropna().unique())
        answer = (f"تغطي البيانات المحددة **{'، '.join(_display_country(v, True) for v in names)}**."
                  if arabic else f"The selected data covers **{', '.join(names)}**.")
        return _result(answer, "scope", scope, base)
    if "what time period" in q or "dataset cover" in q and "period" in q or "الفترة الزمنية" in q:
        names = sorted(str(v) for v in base.get("_timeline", pd.Series(dtype=str)).dropna().unique())
        answer = (f"تغطي البيانات المحددة **{' و'.join(_display_timeline(v, True) for v in names)}**."
                  if arabic else f"The selected data covers **{' and '.join(names)}**.")
        return _result(answer, "scope", scope, base)

    # Exact counts and distributions.
    count_request = bool(re.search(r"how many|\bcount\b|\btotal\b|number of|كم|عدد", q))
    ranking_request = bool(re.search(r"most|largest|highest|leading|top|أكبر|أكثر|الأكثر|ترتيب", q))
    sector_ranking_request = bool(
        re.search(r"sector|industry|قطاع|صناعة", q)
        and re.search(r"which|highest|most|leading|top|أكبر|أكثر|الأكثر|ترتيب", q)
    )
    if count_request and not sector_ranking_request:
        if "compan" in q or "شركة" in q or "شركات" in q:
            count = scoped.get("company", pd.Series(dtype=str)).dropna().replace("", pd.NA).nunique()
            answer = (f"## الشركات الممثلة\n\nتظهر **{count:,} شركة** في النطاق المحدد.\n\n*النطاق: {scope}*"
                      if arabic else
                      f"## Companies represented\n\n**{count:,} companies** appear in the selected scope.\n\n*Scope: {scope}*")
            return _result(answer, "count", scope, scoped)
        role_scoped, role_label = _role_scope(scoped, clean, history)
        by_country = _ALL_COUNTRIES_RE.search(clean) or "in each country" in q or "by country" in q or "حسب الدولة" in q
        if by_country and "_country" in role_scoped.columns:
            counts = role_scoped["_country"].value_counts()
            lines = ([f"## {role_label} حسب الدولة", "", "| الدولة | الإعلانات |", "|---|---:|"]
                     if arabic else
                     [f"## {role_label.title()} by country", "", "| Country | Postings |", "|---|---:|"])
            lines += [f"| {_display_country(str(country), arabic)} | {int(count):,} |" for country, count in counts.items()]
            lines += (["", f"**الإجمالي: {len(role_scoped):,} إعلانًا.**", "", f"*النطاق: {scope}*"]
                      if arabic else ["", f"**Total: {len(role_scoped):,} postings.**", "", f"*Scope: {scope}*"])
            return _result("\n".join(lines), "country-comparison", scope, role_scoped, _job_evidence(role_scoped))
        label = role_label if role_label not in {"all roles", "جميع الوظائف"} else ("إعلانًا وظيفيًا" if arabic else "job postings")
        answer = (f"## إجمالي {label}\n\nيطابق النطاق المحدد **{len(role_scoped):,}** {label}.\n\n*النطاق: {scope}*"
                  if arabic else
                  f"## Total {label}\n\n**{len(role_scoped):,}** {label} match the selected scope.\n\n*Scope: {scope}*")
        return _result(answer, "count", scope, role_scoped, _job_evidence(role_scoped))

    if re.search(r"\b(top|leading|most active|which) (?:companies|company|employers)\b|\bcompanies (?:are )?hiring\b|أكثر الشركات|أبرز الشركات|الشركات.*توظ", q):
        roles, role_label = _role_scope(scoped, clean, history)
        counts = roles.get("company", pd.Series(dtype=str)).dropna().replace("", pd.NA).value_counts().head(10)
        lines = ([f"## أبرز أصحاب العمل في {role_label}", "", "| صاحب العمل | الإعلانات |", "|---|---:|"]
                 if arabic else
                 [f"## Leading employers for {role_label}", "", "| Employer | Postings |", "|---|---:|"])
        lines += [f"| {company} | {int(count):,} |" for company, count in counts.items()]
        lines += (["", "يعكس حجم الإعلانات النشاط في هذه البيانات، وليس ترتيبًا لجودة أصحاب العمل.", "", f"*النطاق: {scope}*"]
                  if arabic else
                  ["", "Posting volume shows activity in this dataset; it is not an employer-quality ranking.", "", f"*Scope: {scope}*"])
        return _result("\n".join(lines), "company-ranking", scope, roles, _job_evidence(roles))

    requested_employment_type = _requested_employment_type(clean)
    requested_group = _requested_group_dimension(clean)
    source_group_requested = requested_group is not None and requested_group[3] == "source"
    if (
        re.search(r"\b(?:compare|comparison|versus|vs\.?|differ(?:ence|ent)?|vary|variation)\b|قارن|مقارنة|اختلاف", q)
        and (("bayt" in q and "linkedin" in q) or source_group_requested)
    ):
        answer = _source_comparison_answer(scoped, clean, history, scope, arabic)
        if answer is not None:
            return answer

    if requested_employment_type and requested_group:
        answer = _employment_by_group_answer(
            scoped,
            requested_employment_type,
            scope,
            arabic,
            requested_group,
        )
        if answer is not None:
            return answer

    # Do not let one-dimensional category summaries swallow questions asking
    # how that category varies across another dimension. Unsupported cross-tabs
    # continue through the full RAG pipeline instead.
    if requested_group and re.search(
        r"\b(?:career level|seniority|entry.level|junior|senior roles|"
        r"languages?|arabic|salary|salaries|pay|compensation|education|degree|bachelor|master|phd|"
        r"gender|women|woman|female|men|man|male|nationali[sz]ation|citizens?)\b|"
        r"متطلبات اللغة|اللغة العربية|راتب|رواتب|تعليم|درجة|بكالوريوس|ماجستير|دكتوراه|"
        r"جنس|نساء|امرأة|رجال|رجل|توطين|مواطن|المستوى الوظيفي|الأقدمية|مبتدئ|وظائف عليا",
        q,
    ):
        return None

    categorical = [
        (r"employment type|full.time|part.time|contract|نوع التوظيف|أنواع التوظيف|دوام كامل|دوام جزئي|عقد", "_employment_norm", "Employment types", "أنواع التوظيف"),
        (r"career level|seniority|entry.level|junior|senior roles|المستوى الوظيفي|الأقدمية|مبتدئ|وظائف عليا", "_career_norm", "Career levels", "المستويات الوظيفية"),
        (r"languages? required|language requirements?|اللغات المطلوبة|متطلبات اللغة", "language", "Language requirements", "متطلبات اللغة"),
    ]
    for pattern, column, title, ar_title in categorical:
        if re.search(pattern, q) and not re.search(r"salary|salaries|pay|compensation|راتب|رواتب", q) and column in scoped.columns:
            counts = scoped[column].dropna().replace("", pd.NA).value_counts().head(10)
            lines = ([f"## {ar_title}", "", "| الفئة | الإعلانات |", "|---|---:|"]
                     if arabic else [f"## {title}", "", "| Category | Postings |", "|---|---:|"])
            lines += [f"| {name} | {int(count):,} |" for name, count in counts.items()]
            lines += ["", f"*النطاق: {scope}*" if arabic else f"*Scope: {scope}*"]
            return _result("\n".join(lines), "category-ranking", scope, scoped)

    # Sector rankings and genuine timeline comparisons.
    if "sector" in q or "industry" in q or re.search(r"hiring changes|what changed|market changes|قطاع|صناعة|تغيرات التوظيف|تغير السوق", q):
        sector_col = "_sector_norm" if "_sector_norm" in scoped.columns else "category"
        if sector_col in scoped.columns and re.search(r"declin|decreas|grew|growing|gain|change|trend|انخفاض|تراجع|نمو|نمت|زاد", q):
            available = _sort_timelines_chrono([str(v) for v in scoped.get("_timeline", pd.Series(dtype=str)).dropna().unique()])
            if len(available) >= 2:
                before, after = available[0], available[-1]
                a, b = scoped[scoped["_timeline"] == before], scoped[scoped["_timeline"] == after]
                ca, cb = a[sector_col].value_counts(), b[sector_col].value_counts()
                rows = []
                for sector in set(ca.index) | set(cb.index):
                    share_a = ca.get(sector, 0) / max(len(a), 1)
                    share_b = cb.get(sector, 0) / max(len(b), 1)
                    rows.append((str(sector), int(ca.get(sector, 0)), int(cb.get(sector, 0)), (share_b - share_a) * 100))
                declining = "declin" in q or "decreas" in q or "انخفاض" in q or "تراجع" in q
                rows.sort(key=lambda row: row[3], reverse=not declining)
                title = (("القطاعات التي تراجعت حصتها" if declining else "القطاعات التي زادت حصتها")
                         if arabic else ("Sectors losing share" if declining else "Sectors gaining share"))
                if arabic:
                    lines = [f"## {title}", "", "تستخدم المقارنة حصة كل قطاع من الإعلانات لأن إجمالي اللقطتين مختلف.", "",
                             f"| القطاع | {_display_timeline(before, True)} | {_display_timeline(after, True)} | تغير الحصة |", "|---|---:|---:|---:|"]
                else:
                    lines = [f"## {title}", "", "Comparison uses each sector’s share of postings because the two snapshots contain different totals.", "", f"| Sector | {before} | {after} | Share change |", "|---|---:|---:|---:|"]
                for sector, c1, c2, change in rows[:8]:
                    lines.append(f"| {sector} | {c1:,} | {c2:,} | {change:+.1f} pp |")
                caveat = _source_caveat(scoped, arabic)
                if caveat:
                    lines += ["", caveat]
                lines += ["", f"*النطاق: {scope}*" if arabic else f"*Scope: {scope}*"]
                return _result("\n".join(lines), "sector-trend", scope, scoped)
        counts = scoped[sector_col].value_counts().head(10)
        lines = (["## أبرز القطاعات", "", "| القطاع | الإعلانات |", "|---|---:|"]
                 if arabic else ["## Leading sectors", "", "| Sector | Postings |", "|---|---:|"])
        lines += [f"| {name} | {int(count):,} |" for name, count in counts.items()]
        lines += ["", f"*النطاق: {scope}*" if arabic else f"*Scope: {scope}*"]
        return _result("\n".join(lines), "sector-ranking", scope, scoped)

    # Skill questions and graduate recommendations. A request to *find jobs*
    # is handled by the lexical job-search route below even if it names skills.
    job_search_request = bool(
        (re.search(r"^(?:find|show|list|search for)\b", q) and re.search(r"\b(job|jobs|role|roles|positions?)\b", q))
        or (re.search(r"^(?:اعثر|ابحث|أظهر|اعرض|اذكر)", q) and re.search(r"وظائف|وظيفة|أدوار|مناصب", q))
    )
    role_requirements = bool(
        re.search(r"requirement|qualification|متطلبات|مؤهلات", q)
        and re.search(r"data analyst|data scientist|data engineer|cybersecurity|cyber security|محلل بيانات|عالم بيانات|الأمن السيبراني", q)
    )
    if not job_search_request and (
        re.search(r"skill|learn|roadmap|recent ai|computer science|programming languages?|python|sql|power\s*bi|excel|javascript|typescript|مهار|خريج|ماذا أتعلم", q)
        or role_requirements
    ):
        return _skills_answer(scoped, clean, history, scope)

    # Country-level demand comparison.
    if re.search(r"compare|which country|hiring demand|opportunities|قارن|أي دولة|طلب التوظيف|فرص", q) and (len(_mentioned_countries(clean)) > 1 or "countr" in q or "selected" in q or "دول" in q or "دولة" in q):
        roles, role_label = _role_scope(scoped, clean, history)
        counts = roles.get("_country", pd.Series(dtype=str)).value_counts()
        lines = ([f"## طلب التوظيف في {role_label}", "", "| الدولة | الإعلانات | الحصة |", "|---|---:|---:|"]
                 if arabic else [f"## Hiring demand for {role_label}", "", "| Country | Postings | Share |", "|---|---:|---:|"])
        for country, count in counts.items():
            lines.append(f"| {_display_country(str(country), arabic)} | {int(count):,} | {count * 100 / max(len(roles), 1):.1f}% |")
        if not counts.empty:
            lines += ["", (f"**تملك {_display_country(str(counts.index[0]), True)} أكبر حجم من الإعلانات في البيانات المحددة.**"
                            if arabic else f"**{counts.index[0]} has the largest posting volume in this selected dataset.**")]
        lines += ["", (f"*تقارن هذه النتيجة حجم الإعلانات، لا الاقتصاد الكلي · {scope}*"
                        if arabic else f"*This compares posting volume, not the overall economy · {scope}*")]
        return _result("\n".join(lines), "country-comparison", scope, roles, _job_evidence(roles))

    # Salary questions: preserve the source currency/unit; never silently mix them.
    if re.search(r"salary|salaries|pay|compensation|راتب|رواتب", q):
        salary_scope, salary_role_label = _role_scope(scoped, clean, history)
        salary_rows = salary_scope[salary_scope.get("salary", pd.Series("", index=salary_scope.index)).fillna("").astype(str).str.strip().ne("")]
        coverage = len(salary_rows) * 100 / max(len(salary_scope), 1)
        lines = ([f"## أدلة الرواتب في {salary_role_label}", "", f"تظهر معلومات الرواتب في **{len(salary_rows):,} من أصل {len(salary_scope):,} إعلانًا مطابقًا ({coverage:.1f}%)**."]
                 if arabic else
                 [f"## Salary evidence for {salary_role_label}", "", f"Salary information appears in **{len(salary_rows):,} of {len(salary_scope):,} matching postings ({coverage:.1f}%)**."])
        if not salary_rows.empty:
            lines += (["", "### أمثلة معلنة", "", "| الوظيفة | الدولة | الراتب المعلن |", "|---|---|---|"]
                      if arabic else
                      ["", "### Advertised examples", "", "| Role | Country | Advertised salary |", "|---|---|---|"])
            for _, row in salary_rows.head(6).iterrows():
                lines.append(f"| {row.get('job_title', '—')} | {_display_country(str(row.get('_country', '—')), arabic)} | {row.get('salary', '—')} |")
        lines += (["", "تُعرض الرواتب كما وردت في الإعلانات. لا ندمج العملات أو فترات الدفع المختلفة في ترتيب واحد مضلل.", "", f"*النطاق: {scope}*"]
                  if arabic else
                  ["", "Salary strings are shown as advertised. Different currencies and pay periods are not combined into one misleading ranking.", "", f"*Scope: {scope}*"])
        return _result("\n".join(lines), "salary", scope, salary_rows, _job_evidence(salary_rows))

    # Strict lexical job discovery prevents an unrelated list from being shown
    # merely because the retriever was asked to fill twelve result slots.
    if job_search_request:
        stop = {
            "find", "show", "list", "search", "for", "job", "jobs", "role", "roles",
            "position", "positions", "in", "the", "a", "an", "requiring", "require",
            "with", "that", "mentioning", "and", "or", "qatar", "uae", "saudi", "arabia", "may", "june",
        }
        terms = [
            token.rstrip(".-")
            for token in re.findall(r"[a-zA-Z][a-zA-Z+#.-]{1,}", q)
            if token.rstrip(".-") not in stop
        ]
        haystack = (
            scoped.get("job_title", pd.Series("", index=scoped.index)).fillna("").astype(str) + " " +
            scoped.get("skills", pd.Series("", index=scoped.index)).fillna("").astype(str) + " " +
            scoped.get("category", pd.Series("", index=scoped.index)).fillna("").astype(str)
        ).str.casefold()
        matches = scoped
        if terms:
            mask = pd.Series(True, index=scoped.index)
            for term in terms:
                mask &= haystack.str.contains(re.escape(term), regex=True, na=False)
            matches = scoped[mask]
        if matches.empty:
            answer = (("## لم تُوجد وظائف مطابقة\n\nلم أجد إعلانًا يحتوي على الوظيفة أو المتطلبات المطلوبة في البيانات المحددة. "
                       "جرّب مسمى أوسع، أو احذف أحد الشروط، أو وسّع الدول والفترات المحددة.\n\n"
                       f"*النطاق الذي تم البحث فيه: {scope}*")
                      if arabic else
                      ("## No matching vacancies found\n\n"
                       "I could not find a posting containing the requested role or requirements in the selected data. "
                       "Try a broader title, remove one requirement, or expand the selected countries and periods.\n\n"
                       f"*Scope searched: {scope}*"))
        else:
            lines = (["## الوظائف المطابقة", "", f"وجدت **{len(matches):,} إعلانًا مطابقًا**. هذه أول ستة:", ""]
                     if arabic else ["## Matching vacancies", "", f"I found **{len(matches):,} matching postings**. Here are the first six:", ""])
            for row in _job_evidence(matches, 6):
                lines.append(f"- **{row['title']}** — {row['company']} · {_display_country(row['country'], arabic)} · {_display_timeline(row['timeline'], arabic)}")
            lines += ["", f"*النطاق: {scope}*" if arabic else f"*Scope: {scope}*"]
            answer = "\n".join(lines)
        return _result(answer, "job-search", scope, matches, _job_evidence(matches))

    return None
