"""
Azure Blob Storage 연결 헬퍼 + /api/health 상태 확인

환경변수:
  AZURE_STORAGE_CONNECTION_STRING
  AZURE_STORAGE_CONTAINER (기본 uploads)
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple

from app.core.config import get_storage_settings

logger = logging.getLogger(__name__)


def is_storage_configured() -> bool:
    return get_storage_settings().is_configured

# Blob Service Client 가져오기
@lru_cache
def get_blob_service_client():
    from azure.storage.blob import BlobServiceClient

    settings = get_storage_settings()
    if not settings.is_configured:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING 이 설정되지 않았습니다.")
    return BlobServiceClient.from_connection_string(settings.connection_string)

# 스토리지 상태 확인
def storage_status() -> dict:
    """헬스체크용 — env + 컨테이너 접근 가능 여부."""
    settings = get_storage_settings()
    if not settings.is_configured:
        return {
            "configured": False,
            "ready": False,
            "container": settings.container,
            "account_name": None,
            "message": "AZURE_STORAGE_CONNECTION_STRING 미설정",
        }

    try:
        client = get_blob_service_client()
        container_client = client.get_container_client(settings.container)

        if not container_client.exists():
            return {
                "configured": True,
                "ready": False,
                "container": settings.container,
                "account_name": _account_name(settings.connection_string),
                "message": f"컨테이너 '{settings.container}' 가 없습니다. Portal에서 Private 컨테이너를 생성하세요.",
            }

        container_client.get_container_properties()
        return {
            "configured": True,
            "ready": True,
            "container": settings.container,
            "account_name": _account_name(settings.connection_string),
            "message": "connected",
        }
    except Exception as exc:
        return {
            "configured": True,
            "ready": False,
            "container": settings.container,
            "account_name": _account_name(settings.connection_string),
            "message": str(exc),
        }

# 계정 이름 추출
def _account_name(connection_string: str) -> Optional[str]:
    for part in connection_string.split(";"):
        if part.strip().lower().startswith("accountname="):
            return part.split("=", 1)[1].strip()
    return None

# 파일명 안전하게 처리
def sanitize_filename(filename: str) -> str:
    """Blob 객체 이름에 쓸 파일명 — 경로 구분자·특수문자 제거."""
    name = Path(filename).name
    safe = re.sub(r"[^\w.\-]", "_", name)
    return safe or "upload.csv"

# Blob 이름 생성
def build_blob_name(upload_id: str, filename: str) -> str:
    """컨테이너 내부 Blob 이름: {upload_id}/{filename}"""
    return f"{upload_id}/{sanitize_filename(filename)}"

# Blob 경로 생성
def build_blob_path(upload_id: str, filename: str) -> str:
    """DB/API용 논리 경로: uploads/{upload_id}/{filename}"""
    settings = get_storage_settings()
    return f"{settings.container}/{build_blob_name(upload_id, filename)}"

# CSV 바이트를 Blob에 업로드
def upload_csv_bytes(*, upload_id: str, filename: str, data: bytes) -> Tuple[str, str]:
    """CSV 바이트를 Blob에 업로드. (blob_path, blob_name) 반환."""
    settings = get_storage_settings()
    if not settings.is_configured:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING 이 설정되지 않았습니다.")

    blob_name = build_blob_name(upload_id, filename)
    blob_path = f"{settings.container}/{blob_name}"

    client = get_blob_service_client()
    blob_client = client.get_blob_client(container=settings.container, blob=blob_name)
    blob_client.upload_blob(data, overwrite=True, content_type="text/csv")
    logger.info("Blob 업로드 완료: %s", blob_path)
    return blob_path, blob_name

# Blob 삭제
def delete_blob(blob_name: str) -> None:
    """분석 완료 후 원본 CSV Blob 삭제. Lifecycle(7일)은 코드 실패 시 백업."""
    settings = get_storage_settings()
    if not settings.is_configured:
        return

    client = get_blob_service_client()
    blob_client = client.get_blob_client(container=settings.container, blob=blob_name)
    blob_client.delete_blob(delete_snapshots="include")
    logger.info("Blob 삭제 완료: %s/%s", settings.container, blob_name)
