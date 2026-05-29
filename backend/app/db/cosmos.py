"""
Azure Cosmos DB (Core/SQL API) client + container 헬퍼

환경변수: .env.example 참고해서 .env 파일 작성해야 함      
파티션 키:
  - upload_history: /upload_id (한 업로드 = 단일 파티션)
"""

from functools import lru_cache
from typing import Optional

from azure.cosmos import ContainerProxy, CosmosClient, DatabaseProxy, PartitionKey
from azure.cosmos.exceptions import CosmosHttpResponseError

from app.core.config import get_cosmos_settings


class CosmosUnavailableError(RuntimeError):
    """Cosmos 환경변수가 비어있거나 초기화 실패 시 발생."""

# CosmosClient 가져오기
@lru_cache
def get_cosmos_client() -> CosmosClient:
    settings = get_cosmos_settings()
    if not settings.is_configured:
        raise CosmosUnavailableError(
            "COSMOS_ENDPOINT / COSMOS_KEY 가 설정되지 않았습니다. "
            "backend/.env (또는 App Service 환경변수) 를 확인하세요."
        )
    return CosmosClient(settings.endpoint, credential=settings.key)

# Database 가져오기
@lru_cache
def get_database() -> DatabaseProxy:
    settings = get_cosmos_settings()
    client = get_cosmos_client()
    return client.create_database_if_not_exists(id=settings.database)

# Upload History Container 가져오기
@lru_cache
def get_upload_history_container() -> ContainerProxy:
    settings = get_cosmos_settings()
    db = get_database()
    return db.create_container_if_not_exists(
        id=settings.container_uploads,
        partition_key=PartitionKey(path="/upload_id"),
    )


# Cosmos 준비 여부 확인
def is_cosmos_ready() -> bool:
    """헬스체크용 — 환경변수 + 실제 연결 모두 검증."""
    try:
        get_upload_history_container()
        return True
    except (CosmosUnavailableError, CosmosHttpResponseError):
        return False
    except Exception:
        return False


# Cosmos Container 가져오기
def safe_container() -> Optional[ContainerProxy]:
    """Cosmos 미설정 시 None 반환. 호출자가 graceful skip 가능."""
    try:
        return get_upload_history_container()
    except CosmosUnavailableError:
        return None
