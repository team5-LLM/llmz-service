"""upload_processor — 월별 split 이력 1건 유지"""

from __future__ import annotations

import unittest

from app.services.upload_history_service import _dedupe_monthly_split_rows
from app.services.upload_processor import _format_month_scope, _merge_summaries
from app.models.upload_history import UploadHistoryDoc, UploadStatus


class UploadProcessorHelperTests(unittest.TestCase):
    def test_format_month_scope_single(self):
        self.assertEqual(_format_month_scope(["2026-05"]), "2026-05")

    def test_format_month_scope_range(self):
        self.assertEqual(
            _format_month_scope(["2026-03", "2026-01", "2026-02"]),
            "2026-01~2026-03",
        )

    def test_merge_summaries(self):
        merged = _merge_summaries(
            [
                {"total_logs": 10, "avg_risk_score": 2.0, "total_cost": 1.0, "departments": 2},
                {"total_logs": 20, "avg_risk_score": 5.0, "total_cost": 3.0, "departments": 3},
            ]
        )
        self.assertEqual(merged["total_logs"], 30)
        self.assertAlmostEqual(merged["avg_risk_score"], 4.0)
        self.assertEqual(merged["total_cost"], 4.0)
        self.assertEqual(merged["departments"], 3)


class DedupeMonthlySplitRowsTests(unittest.TestCase):
    def _doc(self, *, upload_id: str, uploaded_at: str, file_hash: str = "hash-1"):
        doc = UploadHistoryDoc(
            upload_id=upload_id,
            filename="sample.csv",
            file_content_sha256=file_hash,
            uploaded_at=uploaded_at,
        )
        doc.status = UploadStatus.COMPLETED.value
        return doc

    def test_keeps_earliest_completed_in_same_job_window(self):
        docs = [
            self._doc(upload_id="child", uploaded_at="2026-06-05T10:00:02+00:00"),
            self._doc(upload_id="root", uploaded_at="2026-06-05T10:00:00+00:00"),
        ]
        deduped = _dedupe_monthly_split_rows(docs)
        self.assertEqual([d.upload_id for d in deduped], ["root"])

    def test_keeps_separate_uploads_far_apart(self):
        docs = [
            self._doc(upload_id="old", uploaded_at="2026-06-05T10:00:00+00:00"),
            self._doc(upload_id="new", uploaded_at="2026-06-05T12:00:00+00:00"),
        ]
        deduped = _dedupe_monthly_split_rows(docs)
        self.assertEqual(len(deduped), 2)


if __name__ == "__main__":
    unittest.main()
