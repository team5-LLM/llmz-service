"""upload_processor — 월별 split 이력 1건 유지"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services import upload_history_service as history_svc
from app.services.upload_history_service import _dedupe_monthly_split_rows
from app.services.upload_processor import _format_month_scope, _merge_summaries, process_upload_job
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


class CompleteMonthSplitUploadTests(unittest.TestCase):
    def test_creates_completed_child_row(self):
        parent = UploadHistoryDoc(
            upload_id="root-id",
            filename="multi.csv",
            uploaded_by="tester",
            uploaded_at="2026-06-05T10:00:00+00:00",
            file_content_sha256="hash-1",
        )
        parent.push_status(UploadStatus.PROCESSING)

        with patch.object(history_svc, "_upsert", side_effect=lambda doc: doc):
            child = history_svc.complete_month_split_upload(
                upload_id="child-id",
                parent=parent,
                month="2026-06",
                summary={"total_logs": 12, "departments": 3},
                duration_ms=500,
            )

        self.assertIsNotNone(child)
        assert child is not None
        self.assertEqual(child.upload_id, "child-id")
        self.assertEqual(child.department_scope, "2026-06")
        self.assertEqual(child.status, UploadStatus.COMPLETED.value)
        self.assertEqual(child.total_rows, 12)


class ProcessUploadJobMultiMonthTests(unittest.TestCase):
    def test_second_month_registers_completed_upload_history(self):
        parent = UploadHistoryDoc(
            upload_id="job-1",
            filename="multi.csv",
            file_content_sha256="hash-1",
        )
        parent.push_status(UploadStatus.PROCESSING)

        monthly = {
            "2026-05": {
                "summary": {"total_logs": 10},
                "department_stats": [],
                "recommendations": [],
                "masked_logs": [{"log_id": 1, "created_at": "2026-05-01"}],
            },
            "2026-06": {
                "summary": {"total_logs": 8},
                "department_stats": [],
                "recommendations": [],
                "masked_logs": [{"log_id": 2, "created_at": "2026-06-01"}],
            },
        }

        with (
            patch.object(history_svc, "get_upload", return_value=parent),
            patch(
                "app.services.upload_processor.analyze_csv_file",
                return_value={"masked_logs": []},
            ),
            patch(
                "app.services.upload_processor.split_analysis_result_by_month",
                return_value=monthly,
            ),
            patch(
                "app.services.upload_processor.persist_analysis_result",
                return_value=True,
            ) as persist_mock,
            patch.object(history_svc, "complete_month_split_upload") as child_complete_mock,
            patch.object(history_svc, "mark_completed", return_value=parent) as root_complete_mock,
            patch("app.services.upload_processor.is_storage_configured", return_value=False),
        ):
            process_upload_job(
                job_upload_id="job-1",
                tmp_path=Path("dummy.csv"),
                filename="multi.csv",
                file_hash="hash-1",
                content=b"a,b",
                started_monotonic=0.0,
            )

        self.assertEqual(persist_mock.call_count, 2)
        child_complete_mock.assert_called_once()
        root_complete_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
