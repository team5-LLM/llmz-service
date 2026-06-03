"""SCR-DASH-001 — dashboard_service·API 테스트"""

from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.models.upload_history import UploadSummary
from app.services import dashboard_service as svc
from app.utils.date_range import DateRange


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


class DashboardDepartmentDetailTests(unittest.TestCase):
    def test_parse_log_date(self):
        self.assertEqual(svc._parse_log_date("2026-05-04 10:24:00"), date(2026, 5, 4))
        self.assertEqual(svc._parse_log_date("2026-05-04"), date(2026, 5, 4))
        self.assertIsNone(svc._parse_log_date(""))

    def test_trend_bucket_formats(self):
        log_date = date(2026, 5, 4)
        self.assertEqual(svc._trend_bucket(log_date, "daily"), "2026-05-04")
        self.assertEqual(svc._trend_bucket(log_date, "monthly"), "2026-05")
        self.assertRegex(svc._trend_bucket(log_date, "weekly"), r"^\d{4}-W\d{2}$")

    def test_build_trend_from_logs_daily(self):
        logs = [
            SimpleNamespace(
                created_at="2026-05-01 10:00:00",
                total_tokens=100,
                cost=10.5,
                user_hash="u1",
            ),
            SimpleNamespace(
                created_at="2026-05-01 11:00:00",
                total_tokens=200,
                cost=5.0,
                user_hash="u2",
            ),
            SimpleNamespace(
                created_at="2026-05-02 09:00:00",
                total_tokens=50,
                cost=2.0,
                user_hash="u1",
            ),
        ]
        date_range = DateRange(from_date="2026-05-01", to_date="2026-05-31")
        trend = svc._build_trend_from_logs(logs, date_range, "daily")

        self.assertEqual(len(trend), 2)
        self.assertEqual(trend[0].bucket, "2026-05-01")
        self.assertEqual(trend[0].requests, 2)
        self.assertEqual(trend[0].tokens, 300)
        self.assertEqual(trend[0].cost, 15.5)
        self.assertEqual(trend[0].users, 2)
        self.assertEqual(trend[1].requests, 1)
        self.assertEqual(trend[1].users, 1)

    def test_build_tasks_by_priority_sort(self):
        logs = [
            SimpleNamespace(task_label="A", risk_score=10),
            SimpleNamespace(task_label="A", risk_score=20),
            SimpleNamespace(task_label="B", risk_score=30),
        ]
        recommendations = [
            SimpleNamespace(
                task_label="A",
                opportunity_score=50,
                risk_score=15.0,
            ),
            SimpleNamespace(
                task_label="B",
                opportunity_score=90,
                risk_score=30.0,
            ),
        ]

        by_priority = svc._build_tasks_by_priority(logs, recommendations, "priority")
        self.assertEqual(by_priority[0].task_label, "B")
        self.assertEqual(by_priority[0].opportunity_score, 90)

        by_count = svc._build_tasks_by_priority(logs, recommendations, "count")
        self.assertEqual(by_count[0].task_label, "A")
        self.assertEqual(by_count[0].count, 2)
        self.assertAlmostEqual(by_count[0].ratio, 66.7, places=1)

        by_ratio = svc._build_tasks_by_priority(logs, recommendations, "ratio")
        self.assertEqual(by_ratio[0].task_label, "A")


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

    def test_department_detail_not_found_404(self):
        resp = self.client.get("/api/dashboard/departments/없는부서?month=2026-05")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("부서를 찾을 수 없습니다", resp.json()["detail"])

    def test_department_detail_invalid_granularity_422(self):
        resp = self.client.get(
            "/api/dashboard/departments/마케팅팀?month=2026-05&granularity=hourly"
        )
        self.assertEqual(resp.status_code, 422)

    def test_department_detail_invalid_task_sort_422(self):
        resp = self.client.get(
            "/api/dashboard/departments/마케팅팀?month=2026-05&task_sort=name"
        )
        self.assertEqual(resp.status_code, 422)

    def test_department_detail_response_shape(self):
        resp = self.client.get("/api/dashboard/departments/마케팅팀?month=2026-05")
        if resp.status_code == 404:
            return
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["department"], "마케팅팀")
        self.assertIn("overview", body)
        self.assertIn("trend", body)
        self.assertIn("tasks_by_priority", body)
        for task in body["tasks_by_priority"]:
            self.assertGreaterEqual(task["ratio"], 0.0)
            self.assertLessEqual(task["ratio"], 100.0)


if __name__ == "__main__":
    unittest.main()
