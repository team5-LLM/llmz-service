"""dashboard_service — prompt_logs 기간 fallback 복구 테스트."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.services import dashboard_service as svc
from app.utils.date_range import resolve_date_range


class FetchPromptLogRowsFallbackTests(unittest.TestCase):
    def setUp(self):
        self.date_range = resolve_date_range(month="2099-01")

    def _mock_log_row(self, *, upload_id: str, department: str = "마케팅팀"):
        row = MagicMock()
        row.upload_id = upload_id
        row.department = department
        return row

    @patch("app.services.dashboard_service.safe_session")
    def test_returns_primary_rows_when_period_has_logs(self, mock_safe_session):
        session = MagicMock()
        mock_safe_session.return_value = session
        primary = [self._mock_log_row(upload_id="job-1")]

        with patch.object(
            svc,
            "_query_prompt_logs_in_created_at_range",
            return_value=primary,
        ) as mock_primary:
            rows = svc.fetch_prompt_log_rows_in_range(self.date_range)

        self.assertEqual(rows, primary)
        mock_primary.assert_called_once()
        session.scalar.assert_not_called()

    @patch("app.services.dashboard_service.safe_session")
    def test_falls_back_to_latest_completed_upload(self, mock_safe_session):
        session = MagicMock()
        mock_safe_session.return_value = session
        fallback_rows = [
            self._mock_log_row(upload_id="latest-job"),
            self._mock_log_row(upload_id="latest-job"),
        ]

        with patch.object(
            svc,
            "_query_prompt_logs_in_created_at_range",
            return_value=[],
        ), patch.object(
            svc,
            "_latest_completed_upload_id",
            return_value="latest-job",
        ) as mock_latest, patch.object(
            svc,
            "_query_prompt_logs_for_upload",
            return_value=fallback_rows,
        ) as mock_fallback:
            rows = svc.fetch_prompt_log_rows_in_range(self.date_range)

        self.assertEqual(rows, fallback_rows)
        mock_latest.assert_called_once_with(session)
        mock_fallback.assert_called_once_with(
            session,
            "latest-job",
            department=None,
        )

    @patch("app.services.dashboard_service.safe_session")
    def test_returns_empty_when_no_logs_and_no_completed_upload(self, mock_safe_session):
        session = MagicMock()
        mock_safe_session.return_value = session

        with patch.object(
            svc,
            "_query_prompt_logs_in_created_at_range",
            return_value=[],
        ), patch.object(
            svc,
            "_latest_completed_upload_id",
            return_value=None,
        ):
            rows = svc.fetch_prompt_log_rows_in_range(self.date_range)

        self.assertEqual(rows, [])

    @patch("app.services.dashboard_service.fetch_prompt_log_rows_in_range")
    def test_resolve_upload_ids_uses_fallback_rows(self, mock_fetch):
        mock_fetch.return_value = [
            self._mock_log_row(upload_id="latest-job"),
            self._mock_log_row(upload_id="latest-job"),
        ]

        upload_ids = svc.resolve_upload_ids(self.date_range)

        self.assertEqual(upload_ids, ["latest-job"])


if __name__ == "__main__":
    unittest.main()
