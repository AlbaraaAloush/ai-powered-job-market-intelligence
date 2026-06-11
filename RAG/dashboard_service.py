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
    "company_size": "company_size",
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

        if dimension == "location":
            values = _city_series(df)
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
                "company_size": "company_size",
                "language": "language",
                "country": "_country",
            }[dimension]
            if column not in df.columns:
                return []
            values = df[column]

        counts = values.dropna().loc[lambda series: series.astype(str).str.strip() != ""].value_counts()
        return [{"label": _json_value(label), "count": int(count)} for label, count in counts.items()]

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
