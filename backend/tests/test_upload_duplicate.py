"""파일 해시 중복 검사 — processing 차단 포함"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.models.upload_history import UploadStatus
from app.services.upload_history_service import find_blocking_upload_by_file_hash


class FindBlockingUploadByFileHashTests(unittest.TestCase):
    def _mock_row(self, *, upload_id: str, status: str, department_scope: str = "ALL"):
        row = MagicMock()
        row.upload_id = upload_id
        row.filename = "sample.csv"
        row.uploaded_at = "2026-06-05T10:00:00+00:00"
        row.department_scope = department_scope
        row.status = status
        return row

    @patch("app.services.upload_history_service.safe_session")
    def test_blocks_processing_upload(self, mock_safe_session):
        session = MagicMock()
        mock_safe_session.return_value = session
        session.scalars.return_value.all.return_value = [
            self._mock_row(upload_id="job-1", status=UploadStatus.PROCESSING.value),
        ]

        result = find_blocking_upload_by_file_hash("abc123")

        self.assertIsNotNone(result)
        self.assertEqual(result.blocking_reason, "in_progress")
        self.assertEqual(result.upload_ids, ["job-1"])

    @patch("app.services.upload_history_service.safe_session")
    def test_blocks_completed_upload(self, mock_safe_session):
        session = MagicMock()
        mock_safe_session.return_value = session
        session.scalars.return_value.all.return_value = [
            self._mock_row(
                upload_id="done-1",
                status=UploadStatus.COMPLETED.value,
                department_scope="2026-05",
            ),
        ]

        result = find_blocking_upload_by_file_hash("abc123")

        self.assertIsNotNone(result)
        self.assertEqual(result.blocking_reason, "completed")

    @patch("app.services.upload_history_service.safe_session")
    def test_in_progress_takes_priority_over_completed(self, mock_safe_session):
        session = MagicMock()
        mock_safe_session.return_value = session
        session.scalars.return_value.all.return_value = [
            self._mock_row(upload_id="done-1", status=UploadStatus.COMPLETED.value),
            self._mock_row(upload_id="job-1", status=UploadStatus.PROCESSING.value),
        ]

        result = find_blocking_upload_by_file_hash("abc123")

        self.assertEqual(result.blocking_reason, "in_progress")
        self.assertEqual(result.upload_ids, ["job-1"])

    @patch("app.services.upload_history_service.safe_session")
    def test_allows_retry_after_failed(self, mock_safe_session):
        session = MagicMock()
        mock_safe_session.return_value = session
        session.scalars.return_value.all.return_value = []

        result = find_blocking_upload_by_file_hash("abc123")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
