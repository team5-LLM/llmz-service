"""SCR-DASH-001 — dashboard_service·API 테스트"""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.models.upload_history import UploadSummary
from app.services import dashboard_service as svc


class DashboardServiceMergeTests(unittest.TestCase):
    def test_merge_summaries_empty(self):
        result = svc._merge_summaries([])
        self.assertEqual(result.total_logs, 0)
        self.assertEqual(result.total_cost, 0.0)

    def test_merge_summaries_weighted_risk(self):
        merged = svc._merge_summaries(
            [
                UploadSummary(
                    total_logs=100,
                    departments=2,
                    total_tokens=1000,
                    total_cost=100.0,
                    avg_risk_score=20.0,
                ),
                UploadSummary(
                    total_logs=50,
                    departments=1,
                    total_tokens=500,
                    total_cost=50.0,
                    avg_risk_score=80.0,
                ),
            ]
        )
        self.assertEqual(merged.total_logs, 150)
        self.assertEqual(merged.total_tokens, 1500)
        self.assertEqual(merged.total_cost, 150.0)
        # (20*100 + 80*50) / 150 = 40
        self.assertEqual(merged.avg_risk_score, 40.0)

    def test_normalize_task_distribution_ratio_0_to_1(self):
        items = svc._normalize_task_distribution(
            [
                {"label": "보고서 작성형", "count": 72},
                {"label": "코드 생성형", "count": 28},
            ]
        )
        self.assertEqual(len(items), 2)
        self.assertAlmostEqual(items[0].ratio + items[1].ratio, 1.0)
        self.assertEqual(items[0].ratio, 0.72)
        self.assertEqual(items[1].ratio, 0.28)

    def test_merge_department_stats_same_department(self):
        rows = [
            {
                "department": "마케팅팀",
                "total_requests": 50,
                "total_tokens": 1000,
                "total_cost": 100.0,
                "user_count": 5,
                "avg_risk_score": 20.0,
                "high_critical_ratio": 10.0,
                "task_distribution": [{"label": "A", "count": 30, "ratio": 60.0}],
            },
            {
                "department": "마케팅팀",
                "total_requests": 50,
                "total_tokens": 2000,
                "total_cost": 200.0,
                "user_count": 7,
                "avg_risk_score": 40.0,
                "high_critical_ratio": 20.0,
                "task_distribution": [{"label": "A", "count": 20, "ratio": 40.0}],
            },
        ]
        merged = svc._merge_department_stats(rows)
        self.assertEqual(len(merged), 1)
        dept = merged[0]
        self.assertEqual(dept.total_requests, 100)
        self.assertEqual(dept.total_tokens, 3000)
        self.assertEqual(dept.avg_risk_score, 30.0)
        self.assertEqual(dept.task_distribution[0].count, 50)
        self.assertEqual(dept.task_distribution[0].ratio, 1.0)


class DashboardApiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_dashboard_summary_default(self):
        resp = self.client.get("/api/dashboard/summary")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("period", body)
        self.assertIn("summary", body)
        self.assertIn("from_date", body["period"])
        self.assertIn("total_logs", body["summary"])

    def test_dashboard_summary_month(self):
        resp = self.client.get("/api/dashboard/summary?month=2026-05")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["period"]["from_date"], "2026-05-01")
        self.assertEqual(resp.json()["period"]["to_date"], "2026-05-31")

    def test_dashboard_departments_empty_or_data(self):
        resp = self.client.get("/api/dashboard/departments?month=2026-05")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("department_stats", body)
        self.assertIsInstance(body["department_stats"], list)
        for stat in body["department_stats"]:
            for task in stat["task_distribution"]:
                self.assertLessEqual(task["ratio"], 1.0)

    def test_invalid_date_range_400(self):
        resp = self.client.get(
            "/api/dashboard/summary?from_date=2026-06-01&to_date=2026-05-01"
        )
        self.assertEqual(resp.status_code, 400)

    def test_invalid_month_422(self):
        resp = self.client.get("/api/dashboard/summary?month=2026-13")
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
