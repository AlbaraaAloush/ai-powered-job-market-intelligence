"""Tests for dashboard drill-down, search, aggregation, and export."""

import pandas as pd
import pytest

from dashboard_service import DashboardDataService, DashboardQuery


@pytest.fixture
def service() -> DashboardDataService:
    return DashboardDataService(pd.DataFrame([
        {
            "job_id": 1, "job_title": "Data Analyst", "company": "Acme",
            "_sector_norm": "Technology", "location": "Doha, Qatar",
            "skills": "Python; SQL", "description": "Build dashboards",
            "salary": "1000-2000 USD/month", "_country": "Qatar",
            "_timeline": "May 2026", "_dump_id": "qatar_may_2026",
            "company_size": "10-49 employees", "education": "Bachelor",
            "gender": "Any", "_remote_signal": False, "_national_signal": False,
        },
        {
            "job_id": 2, "job_title": "Engineer", "company": "BuildCo",
            "_sector_norm": "Engineering", "location": "Dubai, UAE",
            "skills": "Project Management; SQL",
            "description": "Hybrid site delivery role for Emirati nationals",
            "salary": "3000-5000 USD/month", "_country": "UAE",
            "_timeline": "May 2026", "_dump_id": "uae_may_2026",
            "education": "Master", "gender": "Female",
            "_remote_signal": False, "_national_signal": False,
        },
    ]))


def test_search_and_exact_filters(service):
    result = service.filter(DashboardQuery(query="dashboard", country="Qatar"))
    assert result["job_id"].tolist() == [1]


def test_postings_are_paginated(service):
    result = service.postings(DashboardQuery(), page=2, page_size=1)
    assert result["total"] == 2
    assert result["items"][0]["job_id"] == 2


def test_aggregation_returns_full_ranking(service):
    result = service.aggregation(DashboardQuery(), "skill")
    assert result[0] == {"label": "sql", "count": 2}
    assert len(result) == 3


def test_supplementary_dashboard_fields(service):
    result = service.supplementary_analytics(DashboardQuery())
    assert result["education"][0] == {"level": "Bachelor", "count": 1}
    assert result["gender"][0] == {"preference": "Any", "count": 1}
    assert result["remote"] == [{"country": "UAE", "pct": 100.0, "count": 1}]


def test_invalid_dimension_is_rejected(service):
    with pytest.raises(ValueError):
        service.aggregation(DashboardQuery(), "description")


def test_csv_export_contains_all_rows(service):
    payload, content_type = service.posting_export(DashboardQuery(), "csv")
    text = payload.decode("utf-8-sig")
    assert content_type == "text/csv; charset=utf-8"
    assert "Data Analyst" in text
    assert "Engineer" in text
