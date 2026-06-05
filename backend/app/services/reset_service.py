"""데모/개발용 — 업로드·분석 SQL 데이터 전체 초기화."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError

from app.db.blob import is_storage_configured, purge_upload_container
from app.db.sql import SqlUnavailableError, is_sql_configured, session_scope
from app.models.analysis_result_tables import (
    DepartmentStatRow,
    PromptLogRow,
    RecommendationRow,
)
from app.models.upload_history import UploadStatus
from app.models.upload_history_table import UploadHistoryRow

logger = logging.getLogger(__name__)

_IN_PROGRESS_STATUSES = (
    UploadStatus.PENDING.value,
    UploadStatus.PROCESSING.value,
    UploadStatus.MASKING.value,
    UploadStatus.CLASSIFYING.value,
    UploadStatus.SCORING.value,
)

_RESET_TABLES = (
    ("prompt_logs", PromptLogRow),
    ("recommendations", RecommendationRow),
    ("department_stats", DepartmentStatRow),
    ("upload_history", UploadHistoryRow),
)


def _count_rows(session, model) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def reset_all_upload_data(*, purge_blobs: bool = True) -> dict[str, Any]:
    """
    upload_history + prompt_logs + department_stats + recommendations 전부 DELETE.
    masking-rules 등 admin 설정 테이블은 유지.
    """
    if not is_sql_configured():
        return {
            "ok": False,
            "message": "AZURE_SQL_CONNECTION_STRING 미설정 — 초기화할 DB 없음",
        }

    deleted: dict[str, int] = {}
    cancelled_in_progress = 0
    try:
        with session_scope() as session:
            cancelled_in_progress = int(
                session.scalar(
                    select(func.count())
                    .select_from(UploadHistoryRow)
                    .where(UploadHistoryRow.status.in_(_IN_PROGRESS_STATUSES))
                )
                or 0
            )
            for name, model in _RESET_TABLES:
                result = session.execute(delete(model))
                deleted[name] = int(result.rowcount or 0)

            remaining = {
                name: _count_rows(session, model)
                for name, model in _RESET_TABLES
            }
    except SqlUnavailableError as exc:
        logger.error("reset_all_upload_data — SQL 연결 불가: %s", exc)
        return {"ok": False, "message": str(exc)}
    except SQLAlchemyError as exc:
        logger.error("reset_all_upload_data 실패: %s", exc)
        return {"ok": False, "message": f"SQL 초기화 실패: {exc}"}

    if any(count > 0 for count in remaining.values()):
        logger.error("reset_all_upload_data — 삭제 후 잔여 행: %s", remaining)
        return {
            "ok": False,
            "message": "일부 테이블이 비워지지 않았습니다",
            "deleted": deleted,
            "remaining": remaining,
        }

    blobs_deleted = 0
    blob_message = "skipped (storage not configured)"
    if purge_blobs and is_storage_configured():
        try:
            blobs_deleted = purge_upload_container()
            blob_message = "purged"
        except Exception as exc:
            logger.warning("Blob purge 실패 — SQL만 초기화됨: %s", exc)
            blob_message = f"failed: {exc}"

    logger.info("reset_all_upload_data 완료: %s", deleted)
    return {
        "ok": True,
        "deleted": deleted,
        "remaining": remaining,
        "cancelled_in_progress_jobs": cancelled_in_progress,
        "blobs_deleted": blobs_deleted,
        "blob_purge": blob_message,
    }
