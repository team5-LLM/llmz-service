"""CSV 업로드 백그라운드 분석 처리."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from uuid import uuid4

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

_SUM_KEYS_INT = (
    "masked_logs",
    "no_sensitive_logs",
    "rejected_logs",
    "cluster_count",
    "recommendation_count",
)


def _format_month_scope(months: list[str]) -> str:
    if not months:
        return "ALL"
    ordered = sorted(months)
    if len(ordered) == 1:
        return ordered[0]
    return f"{ordered[0]}~{ordered[-1]}"


def _merge_summaries(summaries: list[dict]) -> dict:
    if not summaries:
        return {}
    total_logs = 0
    weighted_risk = 0.0
    total_cost = 0.0
    max_departments = 0
    merged: dict = {key: 0 for key in _SUM_KEYS_INT}

    for summary in summaries:
        logs = int(summary.get("total_logs", 0) or 0)
        total_logs += logs
        weighted_risk += float(summary.get("avg_risk_score", 0) or 0) * logs
        total_cost += float(summary.get("total_cost", 0) or 0)
        max_departments = max(max_departments, int(summary.get("departments", 0) or 0))
        for key in _SUM_KEYS_INT:
            merged[key] += int(summary.get(key, 0) or 0)

    merged["total_logs"] = total_logs
    merged["total_cost"] = total_cost
    merged["departments"] = max_departments
    merged["avg_risk_score"] = weighted_risk / total_logs if total_logs else 0.0
    return merged


def _require_active_job(job_upload_id: str):
    """
    upload_history 행이 없으면 reset 등으로 job이 취소된 상태.
    이 경우 DB에 다시 쓰지 않고 중단한다 (_upsert가 삭제된 id를 재생성하는 것 방지).
    """
    doc = history_svc.get_upload(job_upload_id)
    if doc is None:
        logger.info("업로드 job 중단 — 이력 삭제됨 (upload_id=%s)", job_upload_id)
    return doc


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
    if _require_active_job(job_upload_id) is None:
        return

    blob_name: str | None = None
    blob_owner_id = job_upload_id
    use_primary = True

    try:
        try:
            result = analyze_csv_file(tmp_path)
        except CsvValidationError as exc:
            primary_doc = _require_active_job(job_upload_id)
            if primary_doc is None:
                return
            errors = [ValidationErrorItem(row_index=exc.row_index, errors=exc.errors)]
            history_svc.attach_validation_errors(primary_doc, errors)
            history_svc.mark_validation_failed(
                primary_doc,
                errors=errors,
                error_message=str(exc),
            )
            return

        primary_doc = _require_active_job(job_upload_id)
        if primary_doc is None:
            return

        monthly = split_analysis_result_by_month(result)
        if not monthly:
            history_svc.mark_failed(primary_doc, error_message=_ERR_NO_LOGS)
            return

        duration_ms = int((time.monotonic() - started_monotonic) * 1000)
        upload_ids: list[str] = []
        log_months: list[str] = []
        month_summaries: list[dict] = []

        for month, month_result in monthly.items():
            primary_doc = _require_active_job(job_upload_id)
            if primary_doc is None:
                return

            if use_primary:
                persist_upload_id = job_upload_id
                primary_doc.file_content_sha256 = file_hash
                use_primary = False
            else:
                persist_upload_id = str(uuid4())

            if persist_upload_id == blob_owner_id and blob_name is None:
                if is_storage_configured():
                    try:
                        blob_path, blob_name = upload_csv_bytes(
                            upload_id=persist_upload_id,
                            filename=filename,
                            data=content,
                        )
                        history_svc.record_blob_path(primary_doc, blob_path)
                    except Exception as exc:
                        logger.warning(
                            "Blob 업로드 실패 — SQL persist만 진행 (upload_id=%s): %s",
                            persist_upload_id,
                            exc,
                        )
                        blob_name = None

            summary = month_result.get("summary", {})
            if not persist_analysis_result(persist_upload_id, month_result):
                history_svc.mark_failed(primary_doc, error_message=_ERR_PERSIST)
                return

            if persist_upload_id != job_upload_id:
                if history_svc.complete_month_split_upload(
                    upload_id=persist_upload_id,
                    parent=primary_doc,
                    month=month,
                    summary=summary,
                    duration_ms=duration_ms,
                ) is None:
                    history_svc.mark_failed(primary_doc, error_message=_ERR_PERSIST)
                    return

            upload_ids.append(persist_upload_id)
            log_months.append(month)
            month_summaries.append(summary)

        primary_doc = _require_active_job(job_upload_id)
        if primary_doc is None:
            return

        aggregated = _merge_summaries(month_summaries)
        total_rows = int(aggregated.get("total_logs", 0))
        primary_doc.department_scope = _format_month_scope(log_months)
        history_svc.mark_completed(
            primary_doc,
            summary=aggregated,
            total_rows=total_rows,
            valid_rows=total_rows,
            invalid_rows=0,
            duration_ms=duration_ms,
        )

        logger.info(
            "업로드 분석 완료 (job=%s, upload_ids=%s, months=%s)",
            job_upload_id,
            upload_ids,
            log_months,
        )
    except Exception as exc:
        logger.exception("업로드 분석 실패 (upload_id=%s): %s", job_upload_id, exc)
        primary_doc = _require_active_job(job_upload_id)
        if primary_doc is not None:
            history_svc.mark_failed(primary_doc, error_message=_ERR_ANALYSIS)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

        if blob_name and is_storage_configured():
            blob_owner_doc = _require_active_job(blob_owner_id)
            if blob_owner_doc is not None:
                try:
                    delete_blob(blob_name)
                    history_svc.record_blob_purged(blob_owner_doc)
                except Exception as exc:
                    logger.warning(
                        "Blob 삭제 실패 (upload_id=%s): %s",
                        blob_owner_id,
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
        doc = _require_active_job(job_upload_id)
        if doc is not None:
            history_svc.mark_failed(doc, error_message=_ERR_ANALYSIS)
