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
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal, Optional

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
from app.utils.date_range import DateRange

logger = logging.getLogger(__name__)

# 월별 split 자식 이력(legacy) — 같은 job 으로 묶는 시간 창
_SPLIT_DEDUP_WINDOW_SEC = 600

# summary API by_status 집계 대상
SUMMARY_STATUSES = (
    UploadStatus.COMPLETED.value,
    UploadStatus.PROCESSING.value,
    UploadStatus.PENDING.value,
    UploadStatus.FAILED.value,
)


# 이력 목록 / count / summary 공통 필터 조건
@dataclass(frozen=True)
class UploadHistoryFilters:
    filename_q: Optional[str] = None
    status: Optional[str] = None
    uploaded_by: Optional[str] = None
    date_range: Optional[DateRange] = None

# JSON 직렬화
def _dump_json(value) -> str:
    return json.dumps(value, ensure_ascii=False)

# JSON 역직렬화
def _load_json(raw: str | None, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default

# 데이터베이스 행을 Pydantic 모델로 변환
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
        file_content_sha256=row.file_content_sha256,
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

# list / count / summary — 동일 WHERE (페이징 total 일치 보장)
def _parse_uploaded_at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _dedupe_monthly_split_rows(docs: List[UploadHistoryDoc]) -> List[UploadHistoryDoc]:
    """
    월별 split 시 생성된 자식 upload_history 행을 목록에서 숨김.
    동일 file_hash + filename 이 짧은 시간 안에 여러 건이면 가장 이른 1건만 유지.
    """
    if len(docs) <= 1:
        return docs

    groups: dict[tuple[str, str], list[UploadHistoryDoc]] = defaultdict(list)
    for doc in docs:
        if (
            doc.file_content_sha256
            and doc.status == UploadStatus.COMPLETED.value
        ):
            groups[(doc.file_content_sha256, doc.filename)].append(doc)

    suppress_ids: set[str] = set()
    for group in groups.values():
        if len(group) <= 1:
            continue

        ordered = sorted(group, key=lambda item: item.uploaded_at)
        cluster = [ordered[0]]
        anchor = _parse_uploaded_at(ordered[0].uploaded_at)

        for doc in ordered[1:]:
            ts = _parse_uploaded_at(doc.uploaded_at)
            if (ts - anchor).total_seconds() <= _SPLIT_DEDUP_WINDOW_SEC:
                cluster.append(doc)
            else:
                if len(cluster) > 1:
                    for dup in cluster[1:]:
                        suppress_ids.add(dup.upload_id)
                cluster = [doc]
                anchor = ts

        if len(cluster) > 1:
            for dup in cluster[1:]:
                suppress_ids.add(dup.upload_id)

    if not suppress_ids:
        return docs
    return [doc for doc in docs if doc.upload_id not in suppress_ids]


def _apply_filters(query, filters: UploadHistoryFilters):
    """공통 WHERE 조건 — list/count/summary 집계에 동일 적용."""
    if filters.filename_q:
        query = query.where(
            UploadHistoryRow.filename.ilike(f"%{filters.filename_q}%")
        )
    if filters.status:
        query = query.where(UploadHistoryRow.status == filters.status)
    if filters.uploaded_by:
        query = query.where(UploadHistoryRow.uploaded_by == filters.uploaded_by)
    if filters.date_range:
        query = query.where(
            UploadHistoryRow.uploaded_at >= filters.date_range.from_date
        ).where(
            UploadHistoryRow.uploaded_at < filters.date_range.from_date_exclusive_upper
        )
    return query


# Pydantic 모델을 데이터베이스 행에 적용
def _apply_doc_to_row(row: UploadHistoryRow, doc: UploadHistoryDoc) -> None:
    row.id = doc.id
    row.filename = doc.filename
    row.file_content_sha256 = doc.file_content_sha256
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

# 업로드 이력 저장/업데이트
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

_IN_PROGRESS_STATUSES = frozenset({
    UploadStatus.PENDING.value,
    UploadStatus.PROCESSING.value,
    UploadStatus.MASKING.value,
    UploadStatus.CLASSIFYING.value,
    UploadStatus.SCORING.value,
})

_BLOCKING_STATUSES = _IN_PROGRESS_STATUSES | {UploadStatus.COMPLETED.value}


@dataclass(frozen=True)
class ExistingFileUpload:
    """동일 파일(SHA-256)로 업로드가 차단되는 기존 이력."""

    file_content_sha256: str
    filename: str
    uploaded_at: str
    upload_ids: List[str]
    log_months: List[str]
    blocking_reason: Literal["in_progress", "completed"]


def find_blocking_upload_by_file_hash(
    file_content_sha256: str,
) -> Optional[ExistingFileUpload]:
    """
    동일 해시로 재업로드를 막아야 하는 이력이 있으면 요약 반환.

    - in_progress: pending / processing 등 분석 진행 중
    - completed: 이미 처리 완료
    - failed 는 재시도 허용 → 조회 대상 아님
    """
    session = safe_session()
    if session is None:
        return None

    try:
        query = (
            select(UploadHistoryRow)
            .where(
                UploadHistoryRow.file_content_sha256 == file_content_sha256,
                UploadHistoryRow.status.in_(_BLOCKING_STATUSES),
            )
            .order_by(UploadHistoryRow.uploaded_at.asc())
        )
        rows = session.scalars(query).all()
        if not rows:
            return None

        in_progress = [r for r in rows if r.status in _IN_PROGRESS_STATUSES]
        completed = [r for r in rows if r.status == UploadStatus.COMPLETED.value]
        target_rows = in_progress if in_progress else completed
        first = target_rows[0]

        return ExistingFileUpload(
            file_content_sha256=file_content_sha256,
            filename=first.filename,
            uploaded_at=min(r.uploaded_at for r in target_rows),
            upload_ids=[r.upload_id for r in target_rows],
            log_months=[r.department_scope for r in target_rows],
            blocking_reason="in_progress" if in_progress else "completed",
        )
    except SQLAlchemyError as exc:
        logger.warning("file hash 중복 조회 실패 — skip: %s", exc)
        return None
    finally:
        session.close()


def find_existing_completed_by_file_hash(
    file_content_sha256: str,
) -> Optional[ExistingFileUpload]:
    """하위 호환 — completed 차단만 조회."""
    existing = find_blocking_upload_by_file_hash(file_content_sha256)
    if existing is None or existing.blocking_reason != "completed":
        return None
    return existing


# 업로드 시작 시점 호출
def create_upload(
    *,
    filename: str,
    uploaded_by: str = "anonymous",
    department_scope: str = "ALL",
    file_content_sha256: Optional[str] = None,
) -> UploadHistoryDoc:
    """업로드 시작 시점 호출. status=pending 으로 기록"""
    doc = UploadHistoryDoc(
        filename=filename,
        uploaded_by=uploaded_by,
        department_scope=department_scope,
        file_content_sha256=file_content_sha256,
    )
    doc.push_status(UploadStatus.PENDING, message="업로드 수신")
    _upsert(doc)
    return doc

# 분석 시작 시점 호출
def mark_processing(doc: UploadHistoryDoc, message: str = "분석 시작") -> UploadHistoryDoc:
    doc.push_status(UploadStatus.PROCESSING, message=message)
    _upsert(doc)
    return doc

# 분석 완료 시점 호출
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


def complete_month_split_upload(
    *,
    upload_id: str,
    parent: UploadHistoryDoc,
    month: str,
    summary: dict,
    duration_ms: int,
) -> Optional[UploadHistoryDoc]:
    """
    다월 CSV split 시 2번째 월 이후용 completed upload_history 행 생성.
    prompt_logs.upload_id 가 completed 집합에 포함되도록 한다.
    """
    total_logs = int(summary.get("total_logs", 0) or 0)
    doc = UploadHistoryDoc(
        upload_id=upload_id,
        filename=parent.filename,
        uploaded_by=parent.uploaded_by,
        uploaded_at=parent.uploaded_at,
        file_content_sha256=parent.file_content_sha256,
        department_scope=month,
    )
    doc.push_status(UploadStatus.PENDING, message="월별 split 저장")
    doc.push_status(UploadStatus.PROCESSING, message=f"{month} 분석 저장")
    return mark_completed(
        doc,
        summary=summary,
        total_rows=total_logs,
        valid_rows=total_logs,
        invalid_rows=0,
        duration_ms=duration_ms,
    )

# Blob 경로 기록
def record_blob_path(doc: UploadHistoryDoc, blob_path: str) -> UploadHistoryDoc:
    doc.blob_path = blob_path
    _upsert(doc)
    return doc

# Blob 삭제 시점 기록
def record_blob_purged(doc: UploadHistoryDoc) -> UploadHistoryDoc:
    doc.blob_purged_at = _now_iso()
    _upsert(doc)
    return doc

# 분석 실패 시점 호출
def mark_failed(doc: UploadHistoryDoc, *, error_message: str) -> UploadHistoryDoc:
    doc.error_message = error_message
    doc.completed_at = _now_iso()
    doc.push_status(UploadStatus.FAILED, message=error_message[:200])
    _upsert(doc)
    return doc


# 검증 오류 처리
def attach_validation_errors(
    doc: UploadHistoryDoc, errors: List[ValidationErrorItem]
) -> UploadHistoryDoc:
    doc.validation_errors = errors
    doc.invalid_rows = len(errors)
    _upsert(doc)
    return doc


def mark_validation_failed(
    doc: UploadHistoryDoc,
    *,
    errors: List[ValidationErrorItem],
    error_message: str,
) -> UploadHistoryDoc:
    """스키마 검증 실패 — validation_errors + status=failed."""
    doc.validation_errors = errors
    doc.invalid_rows = len(errors)
    doc.error_message = error_message
    doc.completed_at = _now_iso()
    doc.push_status(UploadStatus.FAILED, message=error_message[:200])
    _upsert(doc)
    return doc


# 업로드 이력 페이징 조회
def list_uploads(
    *,
    limit: int = 50,
    skip: int = 0,
    filters: Optional[UploadHistoryFilters] = None,
) -> List[UploadHistoryDoc]:
    """이력 페이징 조회. 최신 업로드부터 정렬"""
    session = safe_session()
    if session is None:
        logger.warning("SQL 미설정 — list_uploads 빈 결과 반환")
        return []

    filters = filters or UploadHistoryFilters()

    try:
        query = select(UploadHistoryRow).order_by(UploadHistoryRow.uploaded_at.desc())
        query = _apply_filters(query, filters)
        rows = session.scalars(query.offset(int(skip)).limit(int(limit))).all()
        docs = [_row_to_doc(row) for row in rows]
        return _dedupe_monthly_split_rows(docs)
    except SQLAlchemyError as exc:
        logger.error("list_uploads 실패: %s", exc)
        return []
    finally:
        session.close()


# 업로드 이력 총 개수 조회
def count_uploads(*, filters: Optional[UploadHistoryFilters] = None) -> int:
    session = safe_session()
    if session is None:
        return 0

    filters = filters or UploadHistoryFilters()

    try:
        query = select(func.count()).select_from(UploadHistoryRow)
        query = _apply_filters(query, filters)
        return session.scalar(query) or 0
    except SQLAlchemyError as exc:
        logger.error("count_uploads 실패: %s", exc)
        return 0
    finally:
        session.close()


# status별 건수 집계 (GET /api/uploads/history/summary)
def count_uploads_by_status(
    *, filters: Optional[UploadHistoryFilters] = None
) -> dict[str, int]:
    """기간·필터 내 status별 건수. summary API용."""
    empty = {status: 0 for status in SUMMARY_STATUSES}
    session = safe_session()
    if session is None:
        return empty

    filters = filters or UploadHistoryFilters()

    try:
        query = (
            select(UploadHistoryRow.status, func.count())
            .select_from(UploadHistoryRow)
            .group_by(UploadHistoryRow.status)
        )
        query = _apply_filters(query, filters)
        rows = session.execute(query).all()
        counts = dict(empty)
        for status, count in rows:
            if status in counts:
                counts[status] = int(count)
        return counts
    except SQLAlchemyError as exc:
        logger.error("count_uploads_by_status 실패: %s", exc)
        return empty
    finally:
        session.close()

# 업로드 이력 단일 조회
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
