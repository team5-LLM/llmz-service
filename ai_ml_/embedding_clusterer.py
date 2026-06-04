"""
[3.4 / FUNC-PROC-004]
[3.5 / FUNC-PROC-005]

embedding_clusterer.py

기능:
- 마스킹된 프롬프트 masked_text를 embedding vector로 변환
- Azure OpenAI Embedding 사용 가능 시 Azure embedding 사용
- Azure 미설정 또는 비활성화 시 TF-IDF fallback 사용
- KMeans 기반으로 department 내부 또는 전체 기준 sub-clustering 수행
- 각 row에 sub_cluster_id, local_cluster_id, cluster_method, distance_to_centroid 추가

시스템 흐름:
processed_rows
→ cluster_processed_logs()
→ embed_texts()
   → embed_texts_azure() 또는 embed_texts_tfidf()
→ KMeans clustering
→ clustered_rows 반환

관련 기능명세서:
- 3.4 / FUNC-PROC-004: Embedding 생성
- 3.5 / FUNC-PROC-005: 카테고리 내부 Sub-Clustering

Azure 리소스 optional:
- Azure OpenAI Embedding deployment
- 권장 모델: text-embedding-3-small

필요 환경변수 optional:
- USE_AZURE_OPENAI
- USE_AZURE_EMBEDDING
- AZURE_OPENAI_ENDPOINT
- AZURE_OPENAI_KEY
- AZURE_OPENAI_API_VERSION
- AZURE_OPENAI_EMBEDDING_DEPLOYMENT

설치 패키지:
- numpy
- scikit-learn
- openai (optional)
"""

from __future__ import annotations

import math
import os
from dataclasses import asdict, dataclass
from typing import Any, Iterable

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer


@dataclass(frozen=True)
class ClusterAssignment:
    row_index: int
    log_id: str | None
    department: str
    masked_text: str
    macro_category: str | None
    sub_cluster_id: str
    local_cluster_id: int
    cluster_method: str
    distance_to_centroid: float

    def to_dict(self) -> dict:
        return asdict(self)


def _setting(name: str, default: Any = None) -> Any:
    """
    backend/app/core/config.py의 settings가 있으면 우선 사용하고,
    없으면 환경변수를 사용합니다.
    """
    try:
        from app.core.config import settings

        value = getattr(settings, name, None)
        if value not in (None, ""):
            return value
    except Exception:
        pass

    return os.getenv(name, default)


def _bool_setting(name: str, default: bool = False) -> bool:
    value = _setting(name, default)
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_row_value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _get_masked_text(row: Any) -> str:
    value = (
        _get_row_value(row, "masked_text")
        or _get_row_value(row, "masked_prompt")
        or _get_row_value(row, "text")
        or ""
    )
    return str(value)


def _get_department(row: Any) -> str:
    return str(_get_row_value(row, "department", "UNKNOWN"))


def _get_log_id(row: Any) -> str | None:
    value = _get_row_value(row, "log_id", None)
    return None if value is None else str(value)


def _get_macro_category(row: Any) -> str | None:
    value = (
        _get_row_value(row, "category")
        or _get_row_value(row, "task_label")
        or _get_row_value(row, "macro_category")
    )
    return None if value is None else str(value)


def _azure_embedding_client():
    if not _bool_setting("USE_AZURE_OPENAI", default=False):
        return None

    if not _bool_setting("USE_AZURE_EMBEDDING", default=False):
        return None

    endpoint = _setting("AZURE_OPENAI_ENDPOINT")
    key = _setting("AZURE_OPENAI_KEY")

    if not endpoint or not key:
        return None

    from openai import AzureOpenAI

    return AzureOpenAI(
        api_key=key,
        api_version=str(_setting("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")),
        azure_endpoint=endpoint,
    )


def _embedding_deployment() -> str | None:
    return (
        _setting("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        or os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    )


def embed_texts_azure(texts: list[str], batch_size: int = 128) -> np.ndarray | None:
    """
    Azure OpenAI Embedding API 사용.
    실패하면 None 반환하고 fallback으로 넘어갑니다.
    """
    client = _azure_embedding_client()
    deployment = _embedding_deployment()

    if client is None or not deployment:
        return None

    if not texts:
        return np.empty((0, 0), dtype=np.float32)

    vectors: list[list[float]] = []

    try:
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            response = client.embeddings.create(
                model=deployment,
                input=batch,
            )

            # Azure/OpenAI 응답 순서 보존
            vectors.extend([item.embedding for item in response.data])

        return np.array(vectors, dtype=np.float32)

    except Exception:
        return None


def embed_texts_tfidf(texts: list[str]) -> np.ndarray:
    """
    Azure embedding 미연결 상태에서도 데모가 동작하도록 하는 fallback.
    """
    if not texts:
        return np.empty((0, 0), dtype=np.float32)

    vectorizer = TfidfVectorizer(
        max_features=512,
        ngram_range=(1, 2),
        min_df=1,
    )
    matrix = vectorizer.fit_transform(texts)
    return matrix.toarray().astype(np.float32)


def embed_texts(texts: list[str]) -> tuple[np.ndarray, str]:
    azure_vectors = embed_texts_azure(texts)

    if azure_vectors is not None and azure_vectors.size > 0:
        return azure_vectors, "azure_openai_embedding"

    return embed_texts_tfidf(texts), "tfidf_fallback"


def _auto_n_clusters(n_items: int, max_clusters: int = 8) -> int:
    """
    부서별 자동 cluster 수.
    5,000개 / 6개 부서 기준으로 부서당 5~8개 정도가 적당합니다.
    """
    if n_items <= 1:
        return 1

    # sqrt 기반으로 너무 잘게 쪼개지지 않게 제한
    k = int(round(math.sqrt(n_items / 12)))
    k = max(2, k)
    k = min(k, max_clusters, n_items)
    return k


def _cluster_group(
    rows: list[tuple[int, Any]],
    group_name: str,
    n_clusters: int | None,
    max_clusters: int,
) -> list[ClusterAssignment]:
    valid_rows: list[tuple[int, Any, str]] = []

    for row_index, row in rows:
        text = _get_masked_text(row).strip()
        if not text:
            continue
        valid_rows.append((row_index, row, text))

    if not valid_rows:
        return []

    texts = [item[2] for item in valid_rows]
    k = n_clusters if n_clusters is not None else _auto_n_clusters(len(texts), max_clusters)
    k = max(1, min(k, len(texts)))

    if k == 1:
        return [
            ClusterAssignment(
                row_index=row_index,
                log_id=_get_log_id(row),
                department=_get_department(row),
                masked_text=text,
                macro_category=_get_macro_category(row),
                sub_cluster_id=f"{group_name}_cluster_0",
                local_cluster_id=0,
                cluster_method="single_cluster",
                distance_to_centroid=0.0,
            )
            for row_index, row, text in valid_rows
        ]

    vectors, embedding_method = embed_texts(texts)

    model = KMeans(
        n_clusters=k,
        random_state=42,
        n_init=10,
    )

    cluster_ids = model.fit_predict(vectors)
    centers = model.cluster_centers_

    assignments: list[ClusterAssignment] = []

    for (row_index, row, text), cluster_id, vector in zip(valid_rows, cluster_ids, vectors):
        center = centers[int(cluster_id)]
        distance = float(np.linalg.norm(vector - center))

        assignments.append(
            ClusterAssignment(
                row_index=row_index,
                log_id=_get_log_id(row),
                department=_get_department(row),
                masked_text=text,
                macro_category=_get_macro_category(row),
                sub_cluster_id=f"{group_name}_cluster_{int(cluster_id)}",
                local_cluster_id=int(cluster_id),
                cluster_method=f"{embedding_method}_kmeans",
                distance_to_centroid=round(distance, 6),
            )
        )

    return assignments


def cluster_processed_logs(
    processed_rows: list[Any],
    group_by_department: bool = True,
    n_clusters: int | None = None,
    max_clusters_per_group: int = 8,
) -> list[dict]:
    """
    마스킹/상위분류 완료된 row 목록을 받아 세부 cluster를 붙입니다.

    입력 row 예시:
    {
        "log_id": "1",
        "department": "마케팅팀",
        "masked_text": "...",
        "category": "DATA_ANALYSIS",
        "cost": 26.55,
        "risk_score": 30,
        ...
    }

    반환:
    원본 row + sub_cluster_id, local_cluster_id, cluster_method, distance_to_centroid
    """

    indexed_rows = list(enumerate(processed_rows))

    if not group_by_department:
        assignments = _cluster_group(
            rows=indexed_rows,
            group_name="all",
            n_clusters=n_clusters,
            max_clusters=max_clusters_per_group,
        )
    else:
        grouped: dict[str, list[tuple[int, Any]]] = {}

        for row_index, row in indexed_rows:
            dept = _get_department(row)
            grouped.setdefault(dept, []).append((row_index, row))

        assignments = []

        for dept, group_rows in grouped.items():
            safe_dept = dept.replace("/", "_").replace(" ", "_")
            assignments.extend(
                _cluster_group(
                    rows=group_rows,
                    group_name=safe_dept,
                    n_clusters=n_clusters,
                    max_clusters=max_clusters_per_group,
                )
            )

    assignment_by_index = {assignment.row_index: assignment for assignment in assignments}

    output: list[dict] = []

    for row_index, row in indexed_rows:
        base = dict(row) if isinstance(row, dict) else dict(vars(row))
        assignment = assignment_by_index.get(row_index)

        if assignment is None:
            base.update(
                {
                    "sub_cluster_id": None,
                    "local_cluster_id": None,
                    "cluster_method": "not_clustered",
                    "distance_to_centroid": None,
                }
            )
        else:
            base.update(
                {
                    "sub_cluster_id": assignment.sub_cluster_id,
                    "local_cluster_id": assignment.local_cluster_id,
                    "cluster_method": assignment.cluster_method,
                    "distance_to_centroid": assignment.distance_to_centroid,
                }
            )

        output.append(base)

    return output