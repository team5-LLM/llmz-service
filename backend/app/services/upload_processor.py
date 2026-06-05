"""CSV 업로드 백그라운드 분석 처리."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from app.db.blob import delete_blob, is_storage_configured, upload_csv_bytes
from app.models.upload_history import ValidationErrorItem
from app.services import upload_history_service as history_svc
from app.services.analysis_pipeline import analyze_csv_file, split_analysis_result_by_month
from app.services.csv_loader import CsvValidationError
from app.services.persistence_service import persist_analysis_result

logger = logging.getLogger(__name__)

_ERR_NO_LOGS = "No parseable log rows (created_at)"
_ERR_ANALYSIS = "Analysis processing error"
_ERR_PERSIST = "Failed to save analysis results. Verify DB connection."


def process_upload_job(
    *,
    job_upload_id: str,
    tmp_path: Path,
    filename: str,
    file_hash: str,
    content: bytes,
    started_monotonic: float,
) -> None:
    """동기 분석 파이프라인 — ThreadPool에서 실행."""
    primary_doc = history_svc.get_upload(job_upload_id)
    if primary_doc is None:
        logger.error("업로드 job 없음 (upload_id=%s)", job_upload_id)
        return

    blob_name: str | None = None
    blob_owner_doc = primary_doc
    use_primary = True

    try:
        try:
            result = analyze_csv_file(tmp_path)
        except CsvValidationError as exc:
            errors = [ValidationErrorItem(row_index=exc.row_index, errors=exc.errors)]
            history_svc.attach_validation_errors(primary_doc, errors)
            history_svc.mark_validation_failed(
                primary_doc,
                errors=errors,
                error_message=str(exc),
            )
            return

        monthly = split_analysis_result_by_month(result)
        if not monthly:
            history_svc.mark_failed(primary_doc, error_message=_ERR_NO_LOGS)
            return

        duration_ms = int((time.monotonic() - started_monotonic) * 1000)
        upload_ids: list[str] = []
        log_months: list[str] = []

        for month, month_result in monthly.items():
            if use_primary:
                history_doc = primary_doc
                history_doc.department_scope = month
                history_doc.file_content_sha256 = file_hash
                use_primary = False
            else:
                history_doc = history_svc.create_upload(
                    filename=filename,
                    uploaded_by="anonymous",
                    department_scope=month,
                    file_content_sha256=file_hash,
                )

            if blob_owner_doc.upload_id == history_doc.upload_id:
                if is_storage_configured():
                    try:
                        blob_path, blob_name = upload_csv_bytes(
                            upload_id=history_doc.upload_id,
                            filename=filename,
                            data=content,
                        )
                        history_svc.record_blob_path(history_doc, blob_path)
                    except Exception as exc:
                        logger.warning(
                            "Blob 업로드 실패 — SQL persist만 진행 (upload_id=%s): %s",
                            history_doc.upload_id,
                            exc,
                        )
                        blob_name = None

            history_svc.mark_processing(history_doc, message="분석 중")
            summary = month_result.get("summary", {})
            total_rows = int(summary.get("total_logs", 0))

            if not persist_analysis_result(history_doc.upload_id, month_result):
                history_svc.mark_failed(history_doc, error_message=_ERR_PERSIST)
                return

            history_svc.mark_completed(
                history_doc,
                summary=summary,
                total_rows=total_rows,
                valid_rows=total_rows,
                invalid_rows=0,
                duration_ms=duration_ms,
            )
            upload_ids.append(history_doc.upload_id)
            log_months.append(month)

        logger.info(
            "업로드 분석 완료 (job=%s, upload_ids=%s, months=%s)",
            job_upload_id,
            upload_ids,
            log_months,
        )
    except Exception as exc:
        logger.exception("업로드 분석 실패 (upload_id=%s): %s", job_upload_id, exc)
        history_svc.mark_failed(primary_doc, error_message=_ERR_ANALYSIS)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

        if blob_name and is_storage_configured() and blob_owner_doc is not None:
            try:
                delete_blob(blob_name)
                history_svc.record_blob_purged(blob_owner_doc)
            except Exception as exc:
                logger.warning(
                    "Blob 삭제 실패 (upload_id=%s): %s",
                    blob_owner_doc.upload_id,
                    exc,
                )


async def schedule_upload_job(
    *,
    job_upload_id: str,
    tmp_path: Path,
    filename: str,
    file_hash: str,
    content: bytes,
    started_monotonic: float,
) -> None:
    """응답 반환 후 백그라운드 스레드에서 분석 실행."""
    try:
        await asyncio.to_thread(
            process_upload_job,
            job_upload_id=job_upload_id,
            tmp_path=tmp_path,
            filename=filename,
            file_hash=file_hash,
            content=content,
            started_monotonic=started_monotonic,
        )
    except Exception as exc:
        logger.exception("백그라운드 업로드 job 실패 (upload_id=%s): %s", job_upload_id, exc)
        doc = history_svc.get_upload(job_upload_id)
        if doc is not None:
            history_svc.mark_failed(doc, error_message=_ERR_ANALYSIS)
