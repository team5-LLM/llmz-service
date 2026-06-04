"""masked_text embedding 생성 및 department 내부 sub-clustering."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from .common import embed_texts_azure


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


def _get_row_value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _get_masked_text(row: Any) -> str:
    value = _get_row_value(row, "masked_text") or _get_row_value(row, "masked_prompt") or _get_row_value(row, "text") or ""
    return str(value)


def _get_department(row: Any) -> str:
    return str(_get_row_value(row, "department", "UNKNOWN"))


def _get_log_id(row: Any) -> str | None:
    value = _get_row_value(row, "log_id", None)
    return None if value is None else str(value)


def _get_macro_category(row: Any) -> str | None:
    value = _get_row_value(row, "category") or _get_row_value(row, "task_label") or _get_row_value(row, "macro_category")
    return None if value is None else str(value)


def embed_texts_tfidf(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.empty((0, 0), dtype=np.float32)
    vectorizer = TfidfVectorizer(max_features=512, ngram_range=(1, 2), min_df=1)
    matrix = vectorizer.fit_transform(texts)
    return matrix.toarray().astype(np.float32)


def embed_texts(texts: list[str]) -> tuple[np.ndarray, str]:
    azure_vectors = embed_texts_azure(texts, required_flag="USE_AZURE_EMBEDDING")
    if azure_vectors is not None and azure_vectors.size > 0:
        return azure_vectors, "azure_openai_embedding"
    return embed_texts_tfidf(texts), "tfidf_fallback"


def _auto_n_clusters(n_items: int, max_clusters: int = 8) -> int:
    if n_items <= 1:
        return 1
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
        if text:
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

    # 마스킹 후 동일 문장이 많으면 distinct vector 수가 k보다 작을 수 있습니다.
    # 이 경우 KMeans ConvergenceWarning을 피하기 위해 cluster 수를 줄입니다.
    distinct_vectors = np.unique(vectors, axis=0)
    k = max(1, min(k, len(distinct_vectors)))

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
                cluster_method=f"{embedding_method}_single_cluster",
                distance_to_centroid=0.0,
            )
            for row_index, row, text in valid_rows
        ]

    model = KMeans(n_clusters=k, random_state=42, n_init=10)
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
    indexed_rows = list(enumerate(processed_rows))

    if not group_by_department:
        assignments = _cluster_group(indexed_rows, "all", n_clusters, max_clusters_per_group)
    else:
        grouped: dict[str, list[tuple[int, Any]]] = {}
        for row_index, row in indexed_rows:
            grouped.setdefault(_get_department(row), []).append((row_index, row))

        assignments = []
        for dept, group_rows in grouped.items():
            safe_dept = dept.replace("/", "_").replace(" ", "_")
            assignments.extend(_cluster_group(group_rows, safe_dept, n_clusters, max_clusters_per_group))

    assignment_by_index = {assignment.row_index: assignment for assignment in assignments}
    output: list[dict] = []
    for row_index, row in indexed_rows:
        base = dict(row) if isinstance(row, dict) else dict(vars(row))
        assignment = assignment_by_index.get(row_index)
        if assignment is None:
            base.update({"sub_cluster_id": None, "local_cluster_id": None, "cluster_method": "not_clustered", "distance_to_centroid": None})
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
