import unittest

import pandas as pd

from dashboard_service import DashboardDataService, DashboardQuery


class DashboardDataServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = DashboardDataService(pd.DataFrame([
            {
                "job_id": 1, "job_title": "Data Analyst", "company": "Acme",
                "_sector_norm": "Technology", "location": "Doha, Qatar",
                "skills": "Python; SQL", "description": "Build dashboards",
                "salary": "1000-2000 USD/month", "_country": "Qatar",
                "_timeline": "May 2026", "_dump_id": "qatar_may_2026",
                "company_size": "10-49 employees",
                "education": "Bachelor",
                "gender": "Any",
                "_remote_signal": False,
                "_national_signal": False,
            },
            {
                "job_id": 2, "job_title": "Engineer", "company": "BuildCo",
                "_sector_norm": "Engineering", "location": "Dubai, UAE",
                "skills": "Project Management; SQL",
                "description": "Hybrid site delivery role for Emirati nationals",
                "salary": "3000-5000 USD/month", "_country": "UAE",
                "_timeline": "May 2026", "_dump_id": "uae_may_2026",
                "education": "Master",
                "gender": "Female",
                "_remote_signal": False,
                "_national_signal": False,
            },
        ]))

    def test_search_and_exact_filters(self):
        result = self.service.filter(DashboardQuery(query="dashboard", country="Qatar"))
        self.assertEqual(result["job_id"].tolist(), [1])

    def test_skill_filter_matches_complete_skill(self):
        result = self.service.filter(DashboardQuery(skill="sql"))
        self.assertEqual(result["job_id"].tolist(), [1, 2])

    def test_postings_are_paginated(self):
        result = self.service.postings(DashboardQuery(), page=2, page_size=1)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["items"][0]["job_id"], 2)

    def test_aggregation_returns_full_ranking(self):
        result = self.service.aggregation(DashboardQuery(), "skill")
        self.assertEqual(result[0], {"label": "sql", "count": 2})
        self.assertEqual(len(result), 3)

    def test_salary_bracket_filter(self):
        result = self.service.filter(DashboardQuery(salary_bracket="$1.5K-2K"))
        self.assertEqual(result["job_id"].tolist(), [1])

    def test_company_size_filter_uses_chart_bucket(self):
        result = self.service.filter(DashboardQuery(company_size="1–50"))
        self.assertEqual(result["job_id"].tolist(), [1])

    def test_supplementary_dashboard_fields_are_computed(self):
        result = self.service.supplementary_analytics(DashboardQuery())
        self.assertEqual(result["education"][0], {"level": "Bachelor", "count": 1})
        self.assertEqual(result["gender"][0], {"preference": "Any", "count": 1})
        self.assertEqual(result["remote"], [{"country": "UAE", "pct": 100.0, "count": 1}])
        self.assertEqual(
            result["nationalization"],
            [{"country": "UAE", "pct": 100.0, "count": 1}],
        )

    def test_signal_filters_match_postings(self):
        remote = self.service.filter(DashboardQuery(remote="remote"))
        national = self.service.filter(DashboardQuery(nationalization="mentioned"))
        self.assertEqual(remote["job_id"].tolist(), [2])
        self.assertEqual(national["job_id"].tolist(), [2])

    def test_invalid_dimension_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.aggregation(DashboardQuery(), "description")

    def test_csv_export_contains_all_rows(self):
        payload, content_type = self.service.posting_export(DashboardQuery(), "csv")
        text = payload.decode("utf-8-sig")
        self.assertEqual(content_type, "text/csv; charset=utf-8")
        self.assertIn("Data Analyst", text)
        self.assertIn("Engineer", text)


if __name__ == "__main__":
    unittest.main()
