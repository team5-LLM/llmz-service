""" SCR-RISK-001 · SCR-RISK-002 · SCR-RISK-003 — 위험도 API 테스트"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

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
            self.assertEqual(len(result["all_departments"]), 4)
            self.assertEqual(result["all_departments"][0]["department"], "법무팀")
            self.assertEqual(result["all_departments"][1]["department"], "재무팀")
            dept_names = [item["department"] for item in result["all_departments"]]
            self.assertIn("마케팅팀", dept_names)
            self.assertIn("개발팀", dept_names)
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
        self.assertIn("all_departments", body)
        self.assertIn("critical_departments", body)
        self.assertIn("high_departments", body)
        for key in ("critical_count", "high_count", "medium_count", "low_count", "total_departments"):
            self.assertIn(key, body["summary"])


class SensitiveBreakdownTests(unittest.TestCase):
    def test_build_sensitive_breakdown_ratios(self):
        logs = [
            SimpleNamespace(
                pii_detected=True,
                customer_detected=False,
                confidential_detected=True,
                hr_detected=False,
                secret_detected=False,
                financial_detected=False,
                legal_detected=False,
            ),
            SimpleNamespace(
                pii_detected=False,
                customer_detected=True,
                confidential_detected=False,
                hr_detected=False,
                secret_detected=True,
                financial_detected=True,
                legal_detected=False,
            ),
        ]

        breakdown = risk_svc.build_sensitive_breakdown(logs)  # type: ignore[arg-type]
        self.assertEqual(len(breakdown), 5)
        self.assertEqual(breakdown[0].count, 1)
        self.assertEqual(breakdown[1].count, 1)
        self.assertEqual(breakdown[2].count, 1)
        self.assertEqual(breakdown[3].count, 1)
        self.assertEqual(breakdown[4].count, 1)
        self.assertAlmostEqual(sum(item.ratio for item in breakdown), 100.0, places=1)

    def test_build_sensitive_breakdown_empty_logs(self):
        breakdown = risk_svc.build_sensitive_breakdown([])
        self.assertEqual(len(breakdown), 5)
        self.assertTrue(all(item.count == 0 and item.ratio == 0.0 for item in breakdown))


class RiskDepartmentDetailServiceTests(unittest.TestCase):
    def test_department_detail_from_stats_and_logs(self):
        stat = dashboard_svc.DepartmentStatItem(
            department="법무팀",
            total_requests=10,
            total_tokens=100,
            total_cost=1.0,
            user_count=1,
            avg_risk_score=86.4,
            risk_level="Critical",
            high_critical_ratio=64.2,
            task_distribution=[],
        )
        log = SimpleNamespace(
            pii_detected=True,
            customer_detected=False,
            confidential_detected=False,
            hr_detected=False,
            secret_detected=False,
            financial_detected=False,
            legal_detected=False,
        )

        original_depts = dashboard_svc.get_dashboard_departments
        original_logs = dashboard_svc.fetch_prompt_log_rows_in_range

        dashboard_svc.get_dashboard_departments = lambda _dr: [stat]  # type: ignore[method-assign]
        dashboard_svc.fetch_prompt_log_rows_in_range = (  # type: ignore[method-assign]
            lambda _dr, department=None: [log] if department == "법무팀" else []
        )
        try:
            result = risk_svc.get_risk_department_detail(
                "법무팀",
                DateRange(from_date="2026-05-01", to_date="2026-05-31"),
            )
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result["risk_score"], 86.4)
            self.assertEqual(result["risk_level"], "Critical")
            self.assertEqual(result["sensitive_breakdown"][0]["category"], "personal_info")
            self.assertEqual(result["sensitive_breakdown"][0]["count"], 1)
        finally:
            dashboard_svc.get_dashboard_departments = original_depts
            dashboard_svc.fetch_prompt_log_rows_in_range = original_logs

    def test_department_detail_not_found(self):
        original = dashboard_svc.get_dashboard_departments
        dashboard_svc.get_dashboard_departments = lambda _dr: []  # type: ignore[method-assign]
        try:
            result = risk_svc.get_risk_department_detail(
                "없는팀",
                DateRange(from_date="2026-05-01", to_date="2026-05-31"),
            )
            self.assertIsNone(result)
        finally:
            dashboard_svc.get_dashboard_departments = original


class RiskDepartmentDetailApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_risk_department_not_found_404(self):
        resp = self.client.get("/api/risk/departments/없는팀")
        self.assertEqual(resp.status_code, 404)

    def test_risk_department_response_shape(self):
        stat = dashboard_svc.DepartmentStatItem(
            department="테스트팀",
            total_requests=1,
            total_tokens=1,
            total_cost=0.0,
            user_count=1,
            avg_risk_score=10.0,
            risk_level="Low",
            high_critical_ratio=0.0,
            task_distribution=[],
        )
        original_depts = dashboard_svc.get_dashboard_departments
        original_logs = dashboard_svc.fetch_prompt_log_rows_in_range
        dashboard_svc.get_dashboard_departments = lambda _dr: [stat]  # type: ignore[method-assign]
        dashboard_svc.fetch_prompt_log_rows_in_range = lambda _dr, department=None: []  # type: ignore[method-assign]
        try:
            resp = self.client.get("/api/risk/departments/테스트팀")
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertEqual(body["department"], "테스트팀")
            self.assertIn("sensitive_breakdown", body)
            self.assertEqual(len(body["sensitive_breakdown"]), 5)
        finally:
            dashboard_svc.get_dashboard_departments = original_depts
            dashboard_svc.fetch_prompt_log_rows_in_range = original_logs


if __name__ == "__main__":
    unittest.main()
