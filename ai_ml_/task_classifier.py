"""
[3.3 / FUNC-PROC-003]
task_classifier.py

기능:
- masked_text를 6개 상위 업무 유형으로 매핑
- 업무 유형:
  1. REPORT_WRITING
  2. CODE_GENERATION
  3. CUSTOMER_SUPPORT
  4. DOCUMENT_SUMMARY
  5. DATA_ANALYSIS
  6. SEARCH_QA
- 현재는 rule/anchor 기반 fallback 중심
- Azure OpenAI 또는 Azure embedding 기반 분류는 optional
- 세부 반복 업무 패턴은 이 파일이 아니라 embedding_clusterer.py에서 sub-clustering으로 처리

시스템 흐름:
masked_text
→ classify_task(masked_text)
→ CategoryResult(category, confidence, method)
→ department/category 통계 및 cluster profile에 사용

관련 기능명세서:
- 3.3 / FUNC-PROC-003: 업무 유형 분류

Azure 리소스:
- 기본 동작에는 Azure 리소스 불필요
- Azure 기반 분류 사용 시 Azure OpenAI 또는 embedding deployment 필요

필요 환경변수 optional:
- USE_AZURE_OPENAI
- USE_LLM_TASK_CLASSIFICATION
- AZURE_OPENAI_ENDPOINT
- AZURE_OPENAI_KEY
- AZURE_OPENAI_EMBEDDING_DEPLOYMENT

설치 패키지:
- numpy
- scikit-learn
- openai optional
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

from app.core.config import settings


TASK_CATEGORIES = [
    "REPORT_WRITING",
    "CODE_GENERATION",
    "CUSTOMER_SUPPORT",
    "DOCUMENT_SUMMARY",
    "DATA_ANALYSIS",
    "SEARCH_QA",
]


CATEGORY_ANCHORS = {
    "REPORT_WRITING": [
        "보고서 작성",
        "경영진 보고용 문서 작성",
        "월간 업무 보고서 작성",
        "성과 보고서 초안 작성",
        "팀장 보고용 요약 작성",
    ],
    "CODE_GENERATION": [
        "Python 코드 작성",
        "FastAPI API 구현",
        "React 컴포넌트 코드 작성",
        "버그 원인 분석과 수정 코드 제안",
        "단위 테스트 코드 생성",
    ],
    "CUSTOMER_SUPPORT": [
        "고객 문의 답변 작성",
        "FAQ 답변 생성",
        "배송 지연 문의 응대",
        "환불 요청 고객 응대",
        "상담사가 사용할 답변 문구 작성",
    ],
    "DOCUMENT_SUMMARY": [
        "문서 핵심 내용 요약",
        "회의록 요약",
        "계약서 주요 조항 요약",
        "첨부 문서의 쟁점 정리",
        "긴 문서를 bullet로 요약",
    ],
    "DATA_ANALYSIS": [
        "매출 데이터 분석",
        "비용 데이터 기반 인사이트 도출",
        "전환율 증가 감소 원인 분석",
        "지표 기반 개선 액션 제안",
        "사용량 데이터의 이상치와 반복 패턴 분석",
    ],
    "SEARCH_QA": [
        "용어의 의미 설명",
        "개념을 비전공자도 이해할 수 있게 설명",
        "두 기술의 차이 비교",
        "사용 시 주의할 점 설명",
        "간단한 질문에 대한 답변",
    ],
}


@dataclass(frozen=True)
class CategoryResult:
    category: str
    confidence: float
    method: str


@dataclass(frozen=True)
class ClusterResult:
    text: str
    cluster_id: int
    category: str
    confidence: float
    method: str


# ---------------------------------------------------------------------
# Azure OpenAI Embedding Client
# ---------------------------------------------------------------------

def _embedding_client():
    """
    Azure OpenAI embedding client.

    필요한 환경변수:
    - USE_AZURE_OPENAI=true
    - AZURE_OPENAI_ENDPOINT
    - AZURE_OPENAI_KEY
    - AZURE_OPENAI_EMBEDDING_DEPLOYMENT

    기존 설정에 AZURE_OPENAI_EMBEDDING_DEPLOYMENT가 없다면
    AZURE_OPENAI_DEPLOYMENT를 fallback으로 사용한다.
    단, 실제로는 gpt-4o-mini deployment가 아니라 embedding deployment여야 한다.
    예: text-embedding-3-small
    """

    if not settings.USE_AZURE_OPENAI:
        return None

    if not getattr(settings, "USE_LLM_TASK_CLASSIFICATION", False):
        return None

    if not settings.AZURE_OPENAI_ENDPOINT or not settings.AZURE_OPENAI_KEY:
        return None


    from openai import AzureOpenAI

    return AzureOpenAI(
        api_key=settings.AZURE_OPENAI_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    )


def _embedding_deployment_name() -> str | None:
    """
    settings에 embedding 전용 deployment를 추가하는 것을 권장.

    .env 예시:
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
    """

    return (
        getattr(settings, "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", None)
        or os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        or getattr(settings, "AZURE_OPENAI_DEPLOYMENT", None)
    )


def embed_texts_azure(texts: list[str]) -> np.ndarray | None:
    """
    Azure OpenAI Embedding API로 텍스트 목록을 벡터화한다.
    실패하거나 환경변수가 없으면 None 반환.
    """

    client = _embedding_client()
    deployment = _embedding_deployment_name()

    if client is None or not deployment:
        return None

    if not texts:
        return np.empty((0, 0), dtype=np.float32)

    try:
        response = client.embeddings.create(
            model=deployment,
            input=texts,
        )

        vectors = [item.embedding for item in response.data]
        return np.array(vectors, dtype=np.float32)

    except Exception:
        # 운영에서는 logger.warning으로 남기는 것을 권장.
        # Azure가 아직 연결되지 않은 개발 단계에서는 fallback을 사용한다.
        return None


# ---------------------------------------------------------------------
# Local fallback embedding
# ---------------------------------------------------------------------

def embed_texts_rule_fallback(texts: list[str]) -> np.ndarray:
    """
    Azure embedding이 아직 없을 때 데모가 죽지 않도록 사용하는 fallback.

    실제 semantic embedding은 아니지만,
    6개 업무유형 anchor keyword와의 매칭 점수를 feature vector로 만들어
    KMeans가 동작할 수 있게 한다.
    """

    rows: list[list[float]] = []

    for text in texts:
        row: list[float] = []

        for category in TASK_CATEGORIES:
            anchors = CATEGORY_ANCHORS[category]
            score = 0.0

            for anchor in anchors:
                for token in re.split(r"\\s+", anchor):
                    token = token.strip()
                    if token and re.search(re.escape(token), text, flags=re.IGNORECASE):
                        score += 1.0

            row.append(score)

        # 길이/문서성 힌트 추가
        row.append(min(len(text) / 300.0, 3.0))
        row.append(1.0 if "?" in text or "알려줘" in text or "설명" in text else 0.0)
        row.append(1.0 if "보고" in text or "보고서" in text else 0.0)
        row.append(1.0 if "코드" in text or "API" in text or "Python" in text else 0.0)
        row.append(1.0 if "고객" in text or "문의" in text or "FAQ" in text else 0.0)
        row.append(1.0 if "데이터" in text or "지표" in text or "분석" in text else 0.0)

        rows.append(row)

    return np.array(rows, dtype=np.float32)


def embed_texts(texts: list[str]) -> np.ndarray:
    """
    1순위: Azure OpenAI embedding
    2순위: rule fallback embedding
    """

    azure_vectors = embed_texts_azure(texts)
    if azure_vectors is not None and azure_vectors.size > 0:
        return azure_vectors

    return embed_texts_rule_fallback(texts)


# ---------------------------------------------------------------------
# Cluster labeling
# ---------------------------------------------------------------------

def _anchor_texts() -> tuple[list[str], list[str]]:
    labels: list[str] = []
    texts: list[str] = []

    for category, anchors in CATEGORY_ANCHORS.items():
        for anchor in anchors:
            labels.append(category)
            texts.append(anchor)

    return labels, texts


def _label_clusters_by_anchor_similarity(
    vectors: np.ndarray,
    cluster_ids: np.ndarray,
    n_clusters: int,
) -> dict[int, tuple[str, float]]:
    """
    cluster centroid와 업무유형 anchor embedding을 비교해
    각 cluster를 6개 업무유형 중 하나로 라벨링한다.

    반환:
    {
        0: ("REPORT_WRITING", 0.82),
        1: ("CODE_GENERATION", 0.78),
        ...
    }
    """

    anchor_labels, anchor_text_list = _anchor_texts()
    anchor_vectors = embed_texts(anchor_text_list)

    cluster_label_map: dict[int, tuple[str, float]] = {}

    for cluster_id in range(n_clusters):
        member_vectors = vectors[cluster_ids == cluster_id]

        if len(member_vectors) == 0:
            cluster_label_map[cluster_id] = ("SEARCH_QA", 0.0)
            continue

        centroid = member_vectors.mean(axis=0, keepdims=True)

        if centroid.shape[1] != anchor_vectors.shape[1]:
            # Azure embedding과 fallback embedding 차원이 섞이면 안 된다.
            # 방어적으로 SEARCH_QA로 둔다.
            cluster_label_map[cluster_id] = ("SEARCH_QA", 0.30)
            continue

        similarities = cosine_similarity(centroid, anchor_vectors)[0]
        best_index = int(np.argmax(similarities))
        best_label = anchor_labels[best_index]
        best_score = float(similarities[best_index])

        confidence = max(0.0, min(best_score, 1.0))
        cluster_label_map[cluster_id] = (best_label, round(confidence, 4))

    return cluster_label_map


def _ensure_category_coverage(
    cluster_label_map: dict[int, tuple[str, float]],
    n_clusters: int,
) -> dict[int, tuple[str, float]]:
    """
    데모에서 6개 cluster를 6개 업무유형으로 보여주고 싶을 때 사용.

    실제 clustering 결과상 여러 cluster가 같은 category로 매핑될 수 있다.
    이 경우 발표/데모용으로 중복 라벨을 남은 category에 재배정한다.

    운영 분석에서는 이 보정이 과할 수 있으므로 옵션화하는 것을 권장.
    """

    if n_clusters != 6:
        return cluster_label_map

    used: set[str] = set()
    duplicated_cluster_ids: list[int] = []

    for cluster_id in sorted(cluster_label_map):
        category, confidence = cluster_label_map[cluster_id]
        if category in used:
            duplicated_cluster_ids.append(cluster_id)
        else:
            used.add(category)

    missing = [category for category in TASK_CATEGORIES if category not in used]

    for cluster_id, category in zip(duplicated_cluster_ids, missing):
        _, old_conf = cluster_label_map[cluster_id]
        cluster_label_map[cluster_id] = (category, min(old_conf, 0.60))

    return cluster_label_map


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def cluster_tasks(
    masked_texts: list[str],
    n_clusters: int = 6,
    force_six_demo_labels: bool = True,
) -> list[ClusterResult]:
    """
    여러 masked_text를 n개 cluster로 묶고,
    각 cluster를 업무유형 라벨로 매핑한다.

    이 함수가 classification 대체용 메인 함수다.

    사용 예:
        results = cluster_tasks(masked_texts, n_clusters=6)
        for r in results:
            print(r.cluster_id, r.category, r.confidence)
    """

    if not masked_texts:
        return []

    if len(masked_texts) < n_clusters:
        # 데이터가 너무 적으면 KMeans가 불가능하므로 단일 추론 fallback
        return [
            ClusterResult(
                text=text,
                cluster_id=i,
                category=classify_task(text).category,
                confidence=classify_task(text).confidence,
                method="single_fallback",
            )
            for i, text in enumerate(masked_texts)
        ]

    vectors = embed_texts(masked_texts)

    model = KMeans(
        n_clusters=n_clusters,
        random_state=42,
        n_init="auto",
    )

    cluster_ids = model.fit_predict(vectors)

    cluster_label_map = _label_clusters_by_anchor_similarity(
        vectors=vectors,
        cluster_ids=cluster_ids,
        n_clusters=n_clusters,
    )

    if force_six_demo_labels:
        cluster_label_map = _ensure_category_coverage(
            cluster_label_map=cluster_label_map,
            n_clusters=n_clusters,
        )

    results: list[ClusterResult] = []

    for text, cluster_id in zip(masked_texts, cluster_ids):
        category, confidence = cluster_label_map[int(cluster_id)]
        results.append(
            ClusterResult(
                text=text,
                cluster_id=int(cluster_id),
                category=category,
                confidence=confidence,
                method="azure_embedding_kmeans"
                if embed_texts_azure([text]) is not None
                else "rule_embedding_kmeans",
            )
        )

    return results


def classify_task(masked_text: str) -> CategoryResult:
    """
    기존 backend 호환용 단일 문장 함수.

    주의:
    - clustering은 원칙적으로 batch 단위에서 의미가 있다.
    - 단일 문장에서는 anchor similarity 기반으로 가장 가까운 업무유형을 반환한다.
    - 기존 analysis_pipeline.py가 classify_task(masked_text)를 호출하고 있다면
      일단 이 함수로 호환 가능하다.
    """

    if not masked_text:
        return CategoryResult("SEARCH_QA", 0.30, "empty_fallback")

    labels, anchor_text_list = _anchor_texts()

    text_vector = embed_texts([masked_text])
    anchor_vectors = embed_texts(anchor_text_list)

    if text_vector.shape[1] != anchor_vectors.shape[1]:
        return classify_rule_fallback(masked_text)

    similarities = cosine_similarity(text_vector, anchor_vectors)[0]
    best_index = int(np.argmax(similarities))
    best_category = labels[best_index]
    best_score = float(similarities[best_index])

    return CategoryResult(
        category=best_category,
        confidence=round(max(0.0, min(best_score, 1.0)), 4),
        method="azure_embedding_anchor"
        if embed_texts_azure([masked_text]) is not None
        else "rule_embedding_anchor",
    )


# ---------------------------------------------------------------------
# Rule fallback for compatibility
# ---------------------------------------------------------------------

RULES = [
    ("CODE_GENERATION", ["코드", "API", "FastAPI", "React", "Django", "Node.js", "SQLAlchemy", "Python", "버그", "에러", "단위 테스트", "구현", "파싱"]),
    ('CUSTOMER_SUPPORT', ['고객 문의', '상담', 'FAQ', '환불', '배송', '결제 오류', '불만 고객', '후속 안내', '정중한 답변', '공감형 안내', '[CUSTOMER_INFO]', '[EMAIL]', '안내', '확인해줘', '[CUSTOMER_INFO]', '[EMAIL]', '안내', '확인해줘']),
    ("DOCUMENT_SUMMARY", ["요약", "핵심 내용", "bullet", "회의록", "첨부 문서", "주요 쟁점", "계약서의 핵심", "추려줘"]),
    ("DATA_ANALYSIS", ["데이터", "지표", "분석", "이상치", "반복 패턴", "전환율", "클릭률", "매출", "비용", "핵심 인사이트", "증가/감소 원인"]),
    ("REPORT_WRITING", ["보고서", "보고용", "경영진", "팀장", "임원", "1페이지", "성과를", "진행 상황", "초안", "공유할"]),
    ("SEARCH_QA", ["용어", "개념", "차이", "비교", "주의할 점", "설명해줘", "알려줘", "비전공자"]),
]


def classify_rule_fallback(masked_text: str) -> CategoryResult:
    scores = {category: 0 for category in TASK_CATEGORIES}

    for category, keywords in RULES:
        for keyword in keywords:
            if re.search(re.escape(keyword), masked_text, flags=re.IGNORECASE):
                scores[category] += 1

    best = max(scores, key=scores.get)
    score = scores[best]

    if score == 0:
        return CategoryResult("SEARCH_QA", 0.50, "rule_fallback")

    return CategoryResult(
        category=best,
        confidence=round(min(0.55 + score * 0.08, 0.90), 4),
        method="rule_fallback",
    )