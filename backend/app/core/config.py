"""
환경변수 로더
환경변수: .env.example 참고해서 .env 파일 작성해야 함      

운영에서는 App Service 환경변수 / Azure Key Vault로 주입되며,
로컬에서는 backend/.env (gitignore 처리됨) 에서 읽는다.
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_BACKEND_ROOT / ".env", override=False)

# Cosmos 설정
@dataclass(frozen=True)
class CosmosSettings:
    endpoint: str
    key: str
    database: str
    container_uploads: str

    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint and self.key)

# Cosmos 설정 가져오기
@lru_cache
def get_cosmos_settings() -> CosmosSettings:
    return CosmosSettings(
        endpoint=os.getenv("COSMOS_ENDPOINT", "").strip(),
        key=os.getenv("COSMOS_KEY", "").strip(),
        database=os.getenv("COSMOS_DATABASE", "llmz").strip(),
        container_uploads=os.getenv("COSMOS_CONTAINER_UPLOADS", "upload_history").strip(),
    )
