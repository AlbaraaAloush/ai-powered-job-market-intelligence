"""Deterministic dataframe queries for dashboard search, drill-down, and export."""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

import pandas as pd


FILTER_COLUMNS = {
    "country": "_country",
    "timeline": "_timeline",
    "sector": "_sector_norm",
    "company": "company",
    "title": "job_title",
    "career_level": "_career_norm",
    "employment_type": "_employment_norm",
    "experience": "experience",
    "language": "language",
}

AGGREGATION_DIMENSIONS = {
    "sector",
    "skill",
    "company",
    "title",
    "location",
    "career_level",
    "employment_type",
    "experience",
    "company_size",
    "language",
    "country",
    "salary_bracket",
    "salary_sector",
    "education",
    "gender",
    "remote",
    "nationalization",
    "bilingual",
    "arabic_term",
}

SEARCH_COLUMNS = (
    "job_title",
    "company",
    "_sector_norm",
    "category",
    "location",
    "skills",
    "description",
    "qualifications",
)

SIGNAL_PATTERNS = {
    "_remote_signal": re.compile(
        r"\b(?:remote|hybrid|work(?:ing)? from home|wfh|telecommut(?:e|ing))\b"
        r"|(?:عن بعد|من المنزل|عمل مرن)",
        re.IGNORECASE,
    ),
    "_national_signal": re.compile(
        r"\b(?:saudi[sz]ation|emirati[sz]ation|qatar[sz]ation|omanization|"
        r"bahraini[sz]ation|kuwaiti[sz]ation|nitaqat|"
        r"(?:saudi|emirati|qatari|omani|bahraini|kuwaiti)\s+nationals?)\b"
        r"|(?:السعودة|التوطين|القطرنة|التعمين|للمواطنين)",
        re.IGNORECASE,
    ),
}

SIGNAL_TEXT_COLUMNS = (
    "job_title",
    "description",
    "qualifications",
    "original_content",
    "_ar_content",
)

POSTING_COLUMNS = (
    "job_id",
    "job_title",
    "company",
    "_sector_norm",
    "category",
    "location",
    "salary",
    "employment_type",
    "_employment_norm",
    "career_level",
    "_career_norm",
    "experience",
    "company_size",
    "description",
    "skills",
    "qualifications",
    "education",
    "language",
    "url",
    "post_date",
    "_country",
    "_timeline",
    "_dump_id",
)

SALARY_BINS = [0, 500, 1000, 1500, 2000, 3000, 5000, 7500, 10000, 15000, float("inf")]
SALARY_LABELS = [
    "<$500",
    "$500-1K",
    "$1K-1.5K",
    "$1.5K-2K",
    "$2K-3K",
    "$3K-5K",
    "$5K-7.5K",
    "$7.5K-10K",
    "$10K-15K",
    "$15K+",
]

COMPANY_SIZE_BUCKETS = [
    (50, "1–50"),
    (200, "51–200"),
    (500, "201–500"),
    (1_000, "501–1,000"),
    (5_000, "1,001–5,000"),
    (10_000, "5,001–10,000"),
    (50_000, "10,001–50,000"),
]
COMPANY_SIZE_FALLBACK = "50,000+"


def _parse_salary_mid(value) -> float | None:
    if value is None or pd.isna(value) or not str(value).strip():
        return None
    text = str(value)
    nums = re.findall(r"[\d,]+", text)
    if len(nums) < 2:
        return None
    try:
        low, high = (float(n.replace(",", "")) for n in nums[:2])
    except ValueError:
        return None
    if low < 1 or high < 1:
        return None
    if "year" in text.lower() or "annual" in text.lower():
        low, high = low / 12, high / 12
    if any(token in text.upper() for token in ("SAR", " SR", "SR ")):
        low, high = low / 3.75, high / 3.75
    return (low + high) / 2


def _salary_brackets(df: pd.DataFrame) -> pd.Series:
    mids = df["salary"].apply(_parse_salary_mid) if "salary" in df.columns else pd.Series(dtype=float)
    return pd.cut(mids, bins=SALARY_BINS, labels=SALARY_LABELS, right=False)


def _normalise_company_size(value) -> str | None:
    if value is None or pd.isna(value) or not str(value).strip():
        return None
    numbers = [
        int(token.replace(",", ""))
        for token in re.findall(r"[\d,]+", str(value))
        if token.replace(",", "").isdigit()
    ]
    if not numbers:
        return None
    upper_bound = max(numbers)
    for threshold, label in COMPANY_SIZE_BUCKETS:
        if upper_bound <= threshold:
            return label
    return COMPANY_SIZE_FALLBACK


def _company_size_series(df: pd.DataFrame) -> pd.Series:
    if "company_size" not in df.columns:
        return pd.Series(index=df.index, dtype=str)
    return df["company_size"].apply(_normalise_company_size)


def _city_series(df: pd.DataFrame) -> pd.Series:
    if "location" not in df.columns:
        return pd.Series(index=df.index, dtype=str)
    return (
        df["location"]
        .fillna("Unknown")
        .astype(str)
        .str.split(r"·|,", n=1, regex=True)
        .str[0]
        .str.strip()
        .replace("", "Unknown")
    )


def _json_value(value):
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def _split_skills(value) -> list[str]:
    if value is None or pd.isna(value):
        return []
    return [
        skill.strip()
        for skill in re.split(r"[;,|\n/]+", str(value))
        if 1 < len(skill.strip()) < 60
    ]


@dataclass(frozen=True)
class DashboardQuery:
    dumps: tuple[str, ...] = ()
    query: str = ""
    country: str = ""
    timeline: str = ""
    sector: str = ""
    company: str = ""
    title: str = ""
    skill: str = ""
    location: str = ""
    career_level: str = ""
    employment_type: str = ""
    experience: str = ""
    company_size: str = ""
    language: str = ""
    salary_bracket: str = ""
    education: str = ""
    gender: str = ""
    remote: str = ""
    nationalization: str = ""
    bilingual: str = ""
    arabic_term: str = ""


class DashboardDataService:
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def filter(self, query: DashboardQuery) -> pd.DataFrame:
        result = self.df
        if query.dumps and "_dump_id" in result.columns:
            result = result[result["_dump_id"].isin(query.dumps)]

        for field, column in FILTER_COLUMNS.items():
            value = getattr(query, field)
            if value and column in result.columns:
                result = result[result[column].fillna("").astype(str).str.casefold() == value.casefold()]

        if query.skill and "skills" in result.columns:
            needle = query.skill.casefold()
            result = result[result["skills"].apply(
                lambda value: needle in {skill.casefold() for skill in _split_skills(value)}
            )]

        if query.location:
            cities = _city_series(result)
            result = result[cities.str.casefold() == query.location.casefold()]

        if query.company_size:
            sizes = _company_size_series(result)
            result = result[sizes.fillna("").str.casefold() == query.company_size.casefold()]

        if query.education and "education" in result.columns:
            result = result[
                result["education"].fillna("").astype(str).str.casefold()
                == query.education.casefold()
            ]

        if query.gender and "gender" in result.columns:
            result = result[
                result["gender"].fillna("").astype(str).str.casefold()
                == query.gender.casefold()
            ]

        if query.remote:
            if query.remote != "remote":
                raise ValueError("Invalid remote filter")
            result = result[self._signal_mask(result, "_remote_signal")]

        if query.nationalization:
            if query.nationalization != "mentioned":
                raise ValueError("Invalid nationalization filter")
            result = result[self._signal_mask(result, "_national_signal")]

        if query.bilingual:
            has_ar = (
                result["_ar_content"].notna()
                if "_ar_content" in result.columns
                else result.get("_has_ar_content", pd.Series(False, index=result.index)).fillna(False).astype(bool)
            )
            if query.bilingual == "both":
                result = result[has_ar]
            elif query.bilingual == "en_only":
                result = result[~has_ar]
            else:
                raise ValueError("Invalid bilingual filter")

        if query.arabic_term:
            if "_ar_content" not in result.columns:
                return result.iloc[0:0]
            result = result[
                result["_ar_content"].fillna("").astype(str)
                .str.contains(query.arabic_term, case=False, regex=False)
            ]

        if query.salary_bracket:
            if query.salary_bracket not in SALARY_LABELS:
                raise ValueError("Invalid salary bracket")
            brackets = _salary_brackets(result)
            result = result[brackets.astype("object") == query.salary_bracket]

        search = query.query.strip()
        if search:
            available = [col for col in SEARCH_COLUMNS if col in result.columns]
            if available:
                haystack = result[available].fillna("").astype(str).agg(" ".join, axis=1)
                result = result[haystack.str.contains(search, case=False, regex=False)]

        return result

    def postings(self, query: DashboardQuery, page: int, page_size: int) -> dict:
        result = self.filter(query)
        total = len(result)
        start = (page - 1) * page_size
        page_df = result.iloc[start:start + page_size]
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._posting(row) for _, row in page_df.iterrows()],
        }

    def aggregation(self, query: DashboardQuery, dimension: str) -> list[dict]:
        if dimension not in AGGREGATION_DIMENSIONS:
            raise ValueError("Invalid aggregation dimension")
        result = self.filter(query)
        return self._aggregate(result, dimension)

    def supplementary_analytics(self, query: DashboardQuery) -> dict:
        result = self.filter(query)
        education = self._value_counts(result, "education", "level")
        gender = self._value_counts(result, "gender", "preference")

        remote = self._country_signal_rows(result, "_remote_signal")
        nationalization = self._country_signal_rows(result, "_national_signal")

        return {
            "education": education,
            "gender": gender,
            "remote": remote,
            "nationalization": nationalization,
            "bilingual": self._bilingual_rows(result),
            "arabic_terms": self._arabic_term_rows(result),
        }

    def posting_export(self, query: DashboardQuery, format_name: str) -> tuple[bytes, str]:
        rows = [self._posting(row) for _, row in self.filter(query).iterrows()]
        return self._serialize(rows, format_name)

    def aggregation_export(
        self,
        query: DashboardQuery,
        dimension: str,
        format_name: str,
    ) -> tuple[bytes, str]:
        return self._serialize(self.aggregation(query, dimension), format_name)

    @staticmethod
    def _posting(row: pd.Series) -> dict:
        item = {
            column: _json_value(row.get(column))
            for column in POSTING_COLUMNS
            if column in row.index
        }
        item["title"] = item.pop("job_title", None)
        item["sector"] = item.pop("_sector_norm", None) or item.get("category")
        item["country"] = item.pop("_country", None)
        item["timeline"] = item.pop("_timeline", None)
        item["career_level"] = item.pop("_career_norm", None) or item.get("career_level")
        item["employment_type"] = item.pop("_employment_norm", None) or item.get("employment_type")
        item["skills"] = _split_skills(item.get("skills"))
        return item

    def _aggregate(self, df: pd.DataFrame, dimension: str) -> list[dict]:
        if dimension == "skill":
            counter: Counter[str] = Counter()
            if "skills" in df.columns:
                for value in df["skills"]:
                    counter.update(skill.casefold() for skill in _split_skills(value))
            return [{"label": label, "count": count} for label, count in counter.most_common()]

        if dimension == "remote":
            return [
                {"label": row["country"], "pct": row["pct"], "count": row["count"]}
                for row in self._country_signal_rows(df, "_remote_signal")
            ]
        if dimension == "nationalization":
            return [
                {"label": row["country"], "pct": row["pct"], "count": row["count"]}
                for row in self._country_signal_rows(df, "_national_signal")
            ]
        if dimension == "bilingual":
            return [
                {"label": row["country"], **{key: row[key] for key in ("en_only", "ar_only", "both")}}
                for row in self._bilingual_rows(df)
            ]
        if dimension == "arabic_term":
            return [
                {"label": row["term"], "count": row["count"]}
                for row in self._arabic_term_rows(df)
            ]

        if dimension == "location":
            values = _city_series(df)
        elif dimension == "company_size":
            values = _company_size_series(df)
        elif dimension == "salary_bracket":
            values = _salary_brackets(df)
        elif dimension == "salary_sector":
            if "salary" not in df.columns:
                return []
            sec_col = "_sector_norm" if "_sector_norm" in df.columns else "category"
            tmp = pd.DataFrame({"label": df[sec_col], "salary": df["salary"].apply(_parse_salary_mid)})
            grouped = (
                tmp.dropna()
                .groupby("label")["salary"]
                .agg(["mean", "count"])
                .query("count >= 3")
                .sort_values("mean", ascending=False)
            )
            return [
                {"label": label, "avg_usd": round(row["mean"]), "count": int(row["count"])}
                for label, row in grouped.iterrows()
            ]
        else:
            column = {
                "sector": "_sector_norm",
                "company": "company",
                "title": "job_title",
                "career_level": "_career_norm",
                "employment_type": "_employment_norm",
                "experience": "experience",
                "language": "language",
                "country": "_country",
                "education": "education",
                "gender": "gender",
            }[dimension]
            if column not in df.columns:
                return []
            values = df[column]

        counts = values.dropna().loc[lambda series: series.astype(str).str.strip() != ""].value_counts()
        return [{"label": _json_value(label), "count": int(count)} for label, count in counts.items()]

    @staticmethod
    def _signal_mask(df: pd.DataFrame, column: str) -> pd.Series:
        explicit = (
            df[column].fillna(False).astype(bool)
            if column in df.columns
            else pd.Series(False, index=df.index)
        )
        pattern = SIGNAL_PATTERNS.get(column)
        available = [name for name in SIGNAL_TEXT_COLUMNS if name in df.columns]
        if pattern is None or not available:
            return explicit
        text = df[available].fillna("").astype(str).agg(" ".join, axis=1)
        return explicit | text.str.contains(pattern, na=False)

    @staticmethod
    def _value_counts(df: pd.DataFrame, column: str, label: str) -> list[dict]:
        if column not in df.columns:
            return []
        counts = (
            df[column].dropna().astype(str)
            .loc[lambda values: values.str.strip() != ""]
            .value_counts()
        )
        return [{label: value, "count": int(count)} for value, count in counts.items()]

    def _country_signal_rows(self, df: pd.DataFrame, column: str) -> list[dict]:
        if "_country" not in df.columns:
            return []
        rows = []
        for country, group in df.groupby("_country"):
            count = int(self._signal_mask(group, column).sum())
            if count == 0:
                continue
            rows.append({
                "country": country,
                "pct": round(count / len(group) * 100, 1),
                "count": count,
            })
        return rows

    @staticmethod
    def _bilingual_rows(df: pd.DataFrame) -> list[dict]:
        if "_country" not in df.columns:
            return []
        has_ar = (
            df["_ar_content"].notna()
            if "_ar_content" in df.columns
            else df.get("_has_ar_content", pd.Series(False, index=df.index)).fillna(False).astype(bool)
        )
        if not has_ar.any():
            return []
        rows = []
        for country, group in df.groupby("_country"):
            both = int(has_ar.loc[group.index].sum())
            rows.append({
                "country": country,
                "en_only": int(len(group) - both),
                "ar_only": 0,
                "both": both,
            })
        return rows

    @staticmethod
    def _arabic_term_rows(df: pd.DataFrame) -> list[dict]:
        if "_ar_content" not in df.columns:
            return []
        counter: Counter[str] = Counter()
        for text in df["_ar_content"].dropna().astype(str):
            counter.update(re.findall(r"[\u0600-\u06ff]{3,}", text))
        return [
            {"term": term, "count": count}
            for term, count in counter.most_common(30)
        ]

    @staticmethod
    def _serialize(rows: Iterable[dict], format_name: str) -> tuple[bytes, str]:
        materialized = list(rows)
        if format_name == "json":
            return (
                json.dumps(materialized, ensure_ascii=False, indent=2).encode("utf-8"),
                "application/json; charset=utf-8",
            )
        if format_name != "csv":
            raise ValueError("Invalid export format")

        fields: list[str] = []
        for row in materialized:
            for key in row:
                if key not in fields:
                    fields.append(key)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        if fields:
            writer.writeheader()
            for row in materialized:
                writer.writerow({
                    key: " | ".join(value) if isinstance(value, list) else value
                    for key, value in row.items()
                })
        return ("\ufeff" + output.getvalue()).encode("utf-8"), "text/csv; charset=utf-8"
