"""dashboard_service — created_at 기간 재집계 (스냅샷 fallback 없음) 테스트."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.models.upload_history import UploadSummary
from app.services import dashboard_service as svc
from app.utils.date_range import resolve_date_range


class DashboardSummaryTests(unittest.TestCase):
    def setUp(self):
        self.date_range = resolve_date_range(month="2099-01")

    @patch("app.services.dashboard_service._fetch_prompt_logs_strict_created_at")
    def test_uses_created_at_logs_when_present(self, mock_strict):
        row = MagicMock()
        row.log_id = 1
        row.department = "마케팅팀"
        row.user_hash = "u1"
        row.model = "gpt-4o-mini"
        row.input_tokens = 10.0
        row.output_tokens = 5.0
        row.total_tokens = 15.0
        row.cost = 1.0
        row.created_at = "2099-01-15 10:00:00"
        row.masked_prompt = "masked"
        row.task_label = "REPORT_WRITING"
        row.risk_score = 10
        row.risk_level = "Low"
        row.original_prompt_stored = False
        row.original_discard_verified = True
        row.discard_verification_message = "ok"
        row.pii_detected = False
        row.customer_detected = False
        row.confidential_detected = False
        row.financial_detected = False
        row.legal_detected = False
        row.secret_detected = False
        row.hr_detected = False
        row.exposure_detected = False
        mock_strict.return_value = [row]

        summary = svc.get_dashboard_summary(self.date_range)

        self.assertEqual(summary.total_logs, 1)

    @patch("app.services.dashboard_service._fetch_prompt_logs_strict_created_at")
    def test_returns_empty_summary_when_no_created_at_logs(self, mock_strict):
        mock_strict.return_value = []

        summary = svc.get_dashboard_summary(self.date_range)

        self.assertEqual(summary.total_logs, 0)
        self.assertEqual(summary.departments, 0)


class DashboardDepartmentsTests(unittest.TestCase):
    def setUp(self):
        self.date_range = resolve_date_range(month="2099-01")

    @patch("app.services.dashboard_service._fetch_prompt_logs_strict_created_at")
    def test_returns_empty_list_when_no_created_at_logs(self, mock_strict):
        mock_strict.return_value = []

        items = svc.get_dashboard_departments(self.date_range)

        self.assertEqual(items, [])


class SnapshotUploadIdResolutionTests(unittest.TestCase):
    @patch("app.services.dashboard_service.safe_session")
    def test_resolve_snapshot_upload_ids_returns_empty_without_uploaded_at_match(
        self,
        mock_safe_session,
    ):
        session = MagicMock()
        mock_safe_session.return_value = session
        date_range = resolve_date_range(month="2099-01")

        with patch.object(
            svc,
            "_completed_upload_ids_by_uploaded_at",
            return_value=[],
        ), patch.object(
            svc,
            "_latest_completed_upload_id",
            return_value="snap-job",
        ):
            upload_ids = svc._resolve_snapshot_upload_ids(date_range)

        self.assertEqual(upload_ids, ["snap-job"])


if __name__ == "__main__":
    unittest.main()
