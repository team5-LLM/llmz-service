""" SCR-RISK-001 · SCR-RISK-003 — 위험도 API 테스트"""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.services import dashboard_service as dashboard_svc
from app.services import risk_service as risk_svc
from app.utils.date_range import DateRange


class RiskLevelsTests(unittest.TestCase):
    def test_get_risk_levels_static_four(self):
        result = risk_svc.get_risk_levels()
        self.assertEqual(len(result["levels"]), 4)
        levels = [item["level"] for item in result["levels"]]
        self.assertEqual(levels, ["Low", "Medium", "High", "Critical"])

    def test_risk_levels_api(self):
        client = TestClient(app)
        resp = client.get("/api/risk/levels")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["levels"][0]["score_range"], "0~30")


class RiskOverviewServiceTests(unittest.TestCase):
    def test_overview_counts_and_lists(self):
        stats = [
            dashboard_svc.DepartmentStatItem(
                department="법무팀",
                total_requests=10,
                total_tokens=100,
                total_cost=1.0,
                user_count=1,
                avg_risk_score=86.4,
                risk_level="Critical",
                high_critical_ratio=50.0,
                task_distribution=[],
            ),
            dashboard_svc.DepartmentStatItem(
                department="재무팀",
                total_requests=10,
                total_tokens=100,
                total_cost=1.0,
                user_count=1,
                avg_risk_score=73.1,
                risk_level="High",
                high_critical_ratio=30.0,
                task_distribution=[],
            ),
            dashboard_svc.DepartmentStatItem(
                department="마케팅팀",
                total_requests=10,
                total_tokens=100,
                total_cost=1.0,
                user_count=1,
                avg_risk_score=24.0,
                risk_level="Low",
                high_critical_ratio=0.0,
                task_distribution=[],
            ),
            dashboard_svc.DepartmentStatItem(
                department="개발팀",
                total_requests=10,
                total_tokens=100,
                total_cost=1.0,
                user_count=1,
                avg_risk_score=45.0,
                risk_level="Medium",
                high_critical_ratio=10.0,
                task_distribution=[],
            ),
        ]

        original = dashboard_svc.get_dashboard_departments

        def fake_get(_date_range):
            return stats

        dashboard_svc.get_dashboard_departments = fake_get  # type: ignore[method-assign]
        try:
            result = risk_svc.get_risk_overview(
                DateRange(from_date="2026-05-01", to_date="2026-05-31")
            )
            self.assertEqual(result["summary"]["critical_count"], 1)
            self.assertEqual(result["summary"]["high_count"], 1)
            self.assertEqual(result["summary"]["medium_count"], 1)
            self.assertEqual(result["summary"]["low_count"], 1)
            self.assertEqual(result["summary"]["total_departments"], 4)
            self.assertEqual(result["critical_departments"][0]["department"], "법무팀")
            self.assertEqual(result["high_departments"][0]["department"], "재무팀")
        finally:
            dashboard_svc.get_dashboard_departments = original


class RiskOverviewApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_risk_overview_shape(self):
        resp = self.client.get("/api/risk/overview")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("period", body)
        self.assertIn("summary", body)
        self.assertIn("critical_departments", body)
        self.assertIn("high_departments", body)
        for key in ("critical_count", "high_count", "medium_count", "low_count", "total_departments"):
            self.assertIn(key, body["summary"])


if __name__ == "__main__":
    unittest.main()
