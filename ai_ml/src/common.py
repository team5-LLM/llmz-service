"""
common.py

AI/ML 모듈 공통 유틸리티.

정리 목적:
- app.core.config.settings / os.environ 설정 로딩 중복 제거
- AZURE_OPENAI_KEY / AZURE_OPENAI_API_KEY 혼용 흡수
- Azure OpenAI chat / embedding client 생성 중복 제거
- optional dependency가 없어도 rule / TF-IDF fallback으로 동작하도록 방어
"""
from __future__ import annotations

import os
from typing import Any


def get_setting(name: str, default: Any = None) -> Any:
    """settings 객체가 있으면 우선 사용하고, 없으면 환경변수를 사용합니다."""
    try:
        from app.core.config import settings  # type: ignore

        value = getattr(settings, name, None)
        if value not in (None, ""):
            return value
    except Exception:
        pass

    value = os.getenv(name)
    if value not in (None, ""):
        return value

    aliases = {
        "AZURE_OPENAI_KEY": "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_API_KEY": "AZURE_OPENAI_KEY",
    }
    alias = aliases.get(name)
    if alias:
        value = os.getenv(alias)
        if value not in (None, ""):
            return value

    return default


def bool_setting(name: str, default: bool = False) -> bool:
    value = get_setting(name, default)
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def int_setting(name: str, default: int) -> int:
    value = get_setting(name, default)
    try:
        return int(value)
    except Exception:
        return default


def float_setting(name: str, default: float) -> float:
    value = get_setting(name, default)
    try:
        return float(value)
    except Exception:
        return default


def azure_chat_client(required_flag: str | None = None) -> Any | None:
    """
    Azure OpenAI chat client.

    required_flag가 주어지면 해당 플래그가 true일 때만 client를 반환합니다.
    예: USE_LLM_PII_DETECTION, USE_LLM_RECOMMENDATION
    """
    if not bool_setting("USE_AZURE_OPENAI", default=False):
        return None

    if required_flag and not bool_setting(required_flag, default=False):
        return None

    endpoint = get_setting("AZURE_OPENAI_ENDPOINT")
    key = get_setting("AZURE_OPENAI_KEY") or get_setting("AZURE_OPENAI_API_KEY")

    if not endpoint or not key:
        return None

    try:
        from openai import AzureOpenAI
    except Exception:
        return None

    return AzureOpenAI(
        api_key=key,
        api_version=str(get_setting("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")),
        azure_endpoint=endpoint,
    )


def chat_deployment(*preferred_names: str) -> str | None:
    """우선순위대로 deployment 환경변수를 조회합니다."""
    for name in preferred_names:
        value = get_setting(name)
        if value:
            return str(value)

    return (
        get_setting("AZURE_OPENAI_RECOMMENDATION_DEPLOYMENT")
        or get_setting("AZURE_OPENAI_DEPLOYMENT")
        or os.getenv("AZURE_OPENAI_RECOMMENDATION_DEPLOYMENT")
        or os.getenv("AZURE_OPENAI_DEPLOYMENT")
    )


def azure_embedding_client(required_flag: str | None = None) -> Any | None:
    """Azure OpenAI embedding client."""
    if not bool_setting("USE_AZURE_OPENAI", default=False):
        return None

    if required_flag and not bool_setting(required_flag, default=False):
        return None

    endpoint = get_setting("AZURE_OPENAI_ENDPOINT")
    key = get_setting("AZURE_OPENAI_KEY") or get_setting("AZURE_OPENAI_API_KEY")

    if not endpoint or not key:
        return None

    try:
        from openai import AzureOpenAI
    except Exception:
        return None

    return AzureOpenAI(
        api_key=key,
        api_version=str(get_setting("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")),
        azure_endpoint=endpoint,
    )


def embedding_deployment() -> str | None:
    return (
        get_setting("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        or os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    )


def embed_texts_azure(
    texts: list[str],
    batch_size: int = 128,
    required_flag: str | None = "USE_AZURE_EMBEDDING",
) -> Any | None:
    """
    Azure OpenAI Embedding API 사용.
    실패하거나 환경변수가 없으면 None 반환하여 caller가 fallback을 사용합니다.
    """
    client = azure_embedding_client(required_flag=required_flag)
    deployment = embedding_deployment()

    if client is None or not deployment:
        return None

    try:
        import numpy as np
    except Exception:
        return None

    if not texts:
        return np.empty((0, 0), dtype=np.float32)

    vectors: list[list[float]] = []
    try:
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            response = client.embeddings.create(model=deployment, input=batch)
            vectors.extend([item.embedding for item in response.data])
        return np.array(vectors, dtype=np.float32)
    except Exception:
        return None


def risk_level(score: float) -> str:
    """app.services.scoring.risk_level이 없을 때 쓰는 fallback."""
    try:
        from app.services.scoring import risk_level as app_risk_level  # type: ignore

        return str(app_risk_level(score))
    except Exception:
        pass

    if score >= 80:
        return "Critical"
    if score >= 60:
        return "High"
    if score >= 30:
        return "Medium"
    return "Low"
