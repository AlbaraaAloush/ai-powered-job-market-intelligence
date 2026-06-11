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
            },
            {
                "job_id": 2, "job_title": "Engineer", "company": "BuildCo",
                "_sector_norm": "Engineering", "location": "Dubai, UAE",
                "skills": "Project Management; SQL", "description": "Site delivery",
                "salary": "3000-5000 USD/month", "_country": "UAE",
                "_timeline": "May 2026", "_dump_id": "uae_may_2026",
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
