"""
SCR-INPUT-004 - 업로드 이력 저장/조회 서비스

데이터 저장소: Azure Cosmos DB (컨테이너 'upload_history')

설계 원칙:
1. Cosmos 미설정/장애 시 호출자가 graceful 하게 우회할 수 있도록
   write 함수는 None을 반환, read 함수는 빈 결과를 반환합니다.
   (POST /api/upload 가 Cosmos 없어도 분석 자체는 동작해야 함.)
2. Pydantic 모델 ↔ Cosmos dict 변환 책임은 이 서비스가 진다.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError

from app.db.cosmos import safe_container
from app.models.upload_history import (
    UploadHistoryDoc,
    UploadStatus,
    UploadSummary,
    ValidationErrorItem,
    _now_iso,
)

logger = logging.getLogger(__name__)


# ----------------------------- 내부 유틸리티 API -----------------------------

# 업로드 이력 직렬화
def _serialize(doc: UploadHistoryDoc) -> dict:
    """Pydantic → Cosmos JSON-호환 dict"""
    return doc.model_dump(mode="json")

# 업로드 이력 역직렬화
def _deserialize(data: dict) -> UploadHistoryDoc:
    """Cosmos dict → Pydantic. _rid 등 시스템 필드 제거"""
    cleaned = {k: v for k, v in data.items() if not k.startswith("_")}
    return UploadHistoryDoc.model_validate(cleaned)


# 업로드 이력 저장/업데이트
def _upsert(doc: UploadHistoryDoc) -> Optional[UploadHistoryDoc]:
    container = safe_container()
    if container is None:
        logger.warning("Cosmos 미설정 — upload_history upsert skip (upload_id=%s)", doc.upload_id)
        return None
    try:
        container.upsert_item(_serialize(doc))
        return doc
    except CosmosHttpResponseError as e:
        logger.error("upload_history upsert 실패: %s", e)
        return None


# ----------------------------- 쓰기 API -----------------------------


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


# ----------------------------- 읽기 API -----------------------------


def list_uploads(*, limit: int = 50, skip: int = 0) -> List[UploadHistoryDoc]:
    """이력 페이징 조회. 최신 업로드부터 정렬"""
    container = safe_container()
    if container is None:
        logger.warning("Cosmos 미설정 — list_uploads 빈 결과 반환")
        return []

    query = (
        "SELECT * FROM c "
        "ORDER BY c.uploaded_at DESC "
        f"OFFSET {int(skip)} LIMIT {int(limit)}"
    )
    try:
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        return [_deserialize(item) for item in items]
    except CosmosHttpResponseError as e:
        logger.error("list_uploads 실패: %s", e)
        return []


# 업로드 이력 개수 조회
def count_uploads() -> int:
    container = safe_container()
    if container is None:
        return 0
    try:
        result = list(
            container.query_items(
                query="SELECT VALUE COUNT(1) FROM c",
                enable_cross_partition_query=True,
            )
        )
        return int(result[0]) if result else 0
    except CosmosHttpResponseError as e:
        logger.error("count_uploads 실패: %s", e)
        return 0


# 업로드 이력 단일 조회
def get_upload(upload_id: str) -> Optional[UploadHistoryDoc]:
    """upload_id 단일 조회. 파티션 키 = upload_id 라 단일 파티션 조회."""
    container = safe_container()
    if container is None:
        return None

    query = "SELECT * FROM c WHERE c.upload_id = @upload_id"
    params = [{"name": "@upload_id", "value": upload_id}]
    try:
        items = list( 
            container.query_items(
                query=query,
                parameters=params,
                partition_key=upload_id,
            )
        )
        if not items:
            return None
        return _deserialize(items[0])
    except CosmosResourceNotFoundError:
        return None
    except CosmosHttpResponseError as e:
        logger.error("get_upload 실패: %s", e)
        return None
