"""reset-upload-data API 테스트"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class ResetUploadDataApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_requires_confirm_reset(self):
        resp = self.client.post("/api/admin/reset-upload-data?confirm=WRONG")
        self.assertEqual(resp.status_code, 400)

    @patch("app.main.reset_svc.reset_all_upload_data")
    def test_returns_reset_result(self, mock_reset):
        mock_reset.return_value = {
            "ok": True,
            "deleted": {
                "prompt_logs": 10,
                "recommendations": 2,
                "department_stats": 3,
                "upload_history": 4,
            },
            "remaining": {
                "prompt_logs": 0,
                "recommendations": 0,
                "department_stats": 0,
                "upload_history": 0,
            },
            "blobs_deleted": 0,
            "blob_purge": "skipped (storage not configured)",
        }

        resp = self.client.post("/api/admin/reset-upload-data?confirm=RESET")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["deleted"]["upload_history"], 4)
        self.assertEqual(body["remaining"]["prompt_logs"], 0)

    @patch("app.main.reset_svc.reset_all_upload_data")
    def test_returns_503_when_reset_fails(self, mock_reset):
        mock_reset.return_value = {
            "ok": False,
            "message": "SQL 초기화 실패: timeout",
        }

        resp = self.client.post("/api/admin/reset-upload-data?confirm=RESET")
        self.assertEqual(resp.status_code, 503)


if __name__ == "__main__":
    unittest.main()
