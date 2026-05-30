"""
SCR-INPUT-004 - 업로드 이력 저장/조회 서비스

데이터 저장소: Azure SQL Database (테이블 upload_history)

설계 원칙:
1. SQL 미설정/장애 시 호출자가 graceful 하게 우회할 수 있도록
   write 함수는 None을 반환, read 함수는 빈 결과를 반환합니다.
   (POST /api/upload 가 SQL 없어도 분석 자체는 동작해야 함.)
2. Pydantic 모델 ↔ SQLAlchemy row 변환 책임은 이 서비스가 진다.
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.db.sql import safe_session
from app.models.upload_history import (
    StatusEvent,
    UploadHistoryDoc,
    UploadStatus,
    UploadSummary,
    ValidationErrorItem,
    _now_iso,
)
from app.models.upload_history_table import UploadHistoryRow

logger = logging.getLogger(__name__)


def _dump_json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _load_json(raw: str | None, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _row_to_doc(row: UploadHistoryRow) -> UploadHistoryDoc:
    status_history_raw = _load_json(row.status_history_json, [])
    validation_errors_raw = _load_json(row.validation_errors_json, [])
    summary_raw = _load_json(row.summary_json, None)

    return UploadHistoryDoc(
        id=row.id,
        upload_id=row.upload_id,
        filename=row.filename,
        uploaded_at=row.uploaded_at,
        uploaded_by=row.uploaded_by,
        department_scope=row.department_scope,
        total_rows=row.total_rows,
        valid_rows=row.valid_rows,
        invalid_rows=row.invalid_rows,
        validation_errors=[
            ValidationErrorItem.model_validate(item) for item in validation_errors_raw
        ],
        blob_path=row.blob_path,
        blob_purged_at=row.blob_purged_at,
        status=row.status,
        status_history=[StatusEvent.model_validate(item) for item in status_history_raw],
        error_message=row.error_message,
        summary=UploadSummary.model_validate(summary_raw) if summary_raw else None,
        completed_at=row.completed_at,
        duration_ms=row.duration_ms,
    )


def _status_value(status) -> str:
    if isinstance(status, UploadStatus):
        return status.value
    return str(status)


def _apply_doc_to_row(row: UploadHistoryRow, doc: UploadHistoryDoc) -> None:
    row.id = doc.id
    row.filename = doc.filename
    row.uploaded_at = doc.uploaded_at
    row.uploaded_by = doc.uploaded_by
    row.department_scope = doc.department_scope
    row.total_rows = doc.total_rows
    row.valid_rows = doc.valid_rows
    row.invalid_rows = doc.invalid_rows
    row.validation_errors_json = _dump_json(
        [item.model_dump(mode="json") for item in doc.validation_errors]
    )
    row.blob_path = doc.blob_path
    row.blob_purged_at = doc.blob_purged_at
    row.status = _status_value(doc.status)
    row.status_history_json = _dump_json(
        [event.model_dump(mode="json") for event in doc.status_history]
    )
    row.error_message = doc.error_message
    row.summary_json = (
        _dump_json(doc.summary.model_dump(mode="json")) if doc.summary else None
    )
    row.completed_at = doc.completed_at
    row.duration_ms = doc.duration_ms


def _upsert(doc: UploadHistoryDoc) -> Optional[UploadHistoryDoc]:
    session = safe_session()
    if session is None:
        logger.warning("SQL 미설정 — upload_history upsert skip (upload_id=%s)", doc.upload_id)
        return None

    try:
        row = session.get(UploadHistoryRow, doc.upload_id)
        if row is None:
            row = UploadHistoryRow(upload_id=doc.upload_id, id=doc.id)
            session.add(row)

        _apply_doc_to_row(row, doc)
        session.commit()
        return doc
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("upload_history upsert 실패: %s", exc)
        return None
    finally:
        session.close()


def create_upload(
    *,
    filename: str,
    uploaded_by: str = "anonymous",
    department_scope: str = "ALL",
) -> UploadHistoryDoc:
    """업로드 시작 시점 호출. status=pending 으로 기록"""
    doc = UploadHistoryDoc(
        filename=filename,
        uploaded_by=uploaded_by,
        department_scope=department_scope,
    )
    doc.push_status(UploadStatus.PENDING, message="업로드 수신")
    _upsert(doc)
    return doc


def mark_processing(doc: UploadHistoryDoc, message: str = "분석 시작") -> UploadHistoryDoc:
    doc.push_status(UploadStatus.PROCESSING, message=message)
    _upsert(doc)
    return doc


def mark_completed(
    doc: UploadHistoryDoc,
    *,
    summary: dict,
    total_rows: int,
    valid_rows: int,
    invalid_rows: int,
    duration_ms: int,
) -> UploadHistoryDoc:
    doc.summary = UploadSummary.model_validate(summary)
    doc.total_rows = total_rows
    doc.valid_rows = valid_rows
    doc.invalid_rows = invalid_rows
    doc.duration_ms = duration_ms
    doc.completed_at = _now_iso()
    doc.push_status(UploadStatus.COMPLETED, message="분석 완료")
    _upsert(doc)
    return doc


def mark_failed(doc: UploadHistoryDoc, *, error_message: str) -> UploadHistoryDoc:
    doc.error_message = error_message
    doc.completed_at = _now_iso()
    doc.push_status(UploadStatus.FAILED, message=error_message[:200])
    _upsert(doc)
    return doc


def attach_validation_errors(
    doc: UploadHistoryDoc, errors: List[ValidationErrorItem]
) -> UploadHistoryDoc:
    doc.validation_errors = errors
    doc.invalid_rows = len(errors)
    _upsert(doc)
    return doc


def list_uploads(*, limit: int = 50, skip: int = 0) -> List[UploadHistoryDoc]:
    """이력 페이징 조회. 최신 업로드부터 정렬"""
    session = safe_session()
    if session is None:
        logger.warning("SQL 미설정 — list_uploads 빈 결과 반환")
        return []

    try:
        rows = session.scalars(
            select(UploadHistoryRow)
            .order_by(UploadHistoryRow.uploaded_at.desc())
            .offset(int(skip))
            .limit(int(limit))
        ).all()
        return [_row_to_doc(row) for row in rows]
    except SQLAlchemyError as exc:
        logger.error("list_uploads 실패: %s", exc)
        return []
    finally:
        session.close()


def count_uploads() -> int:
    session = safe_session()
    if session is None:
        return 0

    try:
        return session.scalar(select(func.count()).select_from(UploadHistoryRow)) or 0
    except SQLAlchemyError as exc:
        logger.error("count_uploads 실패: %s", exc)
        return 0
    finally:
        session.close()


def get_upload(upload_id: str) -> Optional[UploadHistoryDoc]:
    """upload_id 단일 조회."""
    session = safe_session()
    if session is None:
        return None

    try:
        row = session.get(UploadHistoryRow, upload_id)
        if row is None:
            return None
        return _row_to_doc(row)
    except SQLAlchemyError as exc:
        logger.error("get_upload 실패: %s", exc)
        return None
    finally:
        session.close()
