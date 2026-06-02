"""데모/개발용 — 업로드·분석 SQL 데이터 전체 초기화."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.db.blob import is_storage_configured, purge_upload_container
from app.db.sql import safe_session
from app.models.analysis_result_tables import (
    DepartmentStatRow,
    PromptLogRow,
    RecommendationRow,
)
from app.models.upload_history_table import UploadHistoryRow

logger = logging.getLogger(__name__)


def reset_all_upload_data(*, purge_blobs: bool = True) -> dict[str, Any]:
    """
    upload_history + prompt_logs + department_stats + recommendations 전부 DELETE.
    masking-rules 등 admin 설정 테이블은 유지.
    """
    session = safe_session()
    if session is None:
        return {"ok": False, "message": "Azure SQL 미설정 — 초기화할 데이터 없음"}

    deleted: dict[str, int] = {}
    try:
        deleted["prompt_logs"] = session.query(PromptLogRow).delete()
        deleted["recommendations"] = session.query(RecommendationRow).delete()
        deleted["department_stats"] = session.query(DepartmentStatRow).delete()
        deleted["upload_history"] = session.query(UploadHistoryRow).delete()
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("reset_all_upload_data 실패: %s", exc)
        return {"ok": False, "message": str(exc)}
    finally:
        session.close()

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
        "blobs_deleted": blobs_deleted,
        "blob_purge": blob_message,
    }
