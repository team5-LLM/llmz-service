"""masked_text를 6개 상위 업무 유형으로 매핑."""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

from ai_ml.common import embed_texts_azure
from ai_ml.pii_schema import CategoryResult

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
        "보고서 작성", "경영진 보고용 문서 작성", "월간 업무 보고서 작성", "성과 보고서 초안 작성", "팀장 보고용 요약 작성",
    ],
    "CODE_GENERATION": [
        "Python 코드 작성", "FastAPI API 구현", "React 컴포넌트 코드 작성", "버그 원인 분석과 수정 코드 제안", "단위 테스트 코드 생성",
    ],
    "CUSTOMER_SUPPORT": [
        "고객 문의 답변 작성", "FAQ 답변 생성", "배송 지연 문의 응대", "환불 요청 고객 응대", "상담사가 사용할 답변 문구 작성",
    ],
    "DOCUMENT_SUMMARY": [
        "문서 핵심 내용 요약", "회의록 요약", "계약서 주요 조항 요약", "첨부 문서의 쟁점 정리", "긴 문서를 bullet로 요약",
    ],
    "DATA_ANALYSIS": [
        "매출 데이터 분석", "비용 데이터 기반 인사이트 도출", "전환율 증가 감소 원인 분석", "지표 기반 개선 액션 제안", "사용량 데이터의 이상치와 반복 패턴 분석",
    ],
    "SEARCH_QA": [
        "용어의 의미 설명", "개념을 비전공자도 이해할 수 있게 설명", "두 기술의 차이 비교", "사용 시 주의할 점 설명", "간단한 질문에 대한 답변",
    ],
}


@dataclass(frozen=True)
class ClusterResult:
    text: str
    cluster_id: int
    category: str
    confidence: float
    method: str


def embed_texts_rule_fallback(texts: list[str]) -> np.ndarray:
    rows: list[list[float]] = []
    for text in texts:
        row: list[float] = []
        for category in TASK_CATEGORIES:
            score = 0.0
            for anchor in CATEGORY_ANCHORS[category]:
                for token in re.split(r"\s+", anchor):
                    token = token.strip()
                    if token and re.search(re.escape(token), text, flags=re.IGNORECASE):
                        score += 1.0
            row.append(score)

        row.append(min(len(text) / 300.0, 3.0))
        row.append(1.0 if "?" in text or "알려줘" in text or "설명" in text else 0.0)
        row.append(1.0 if "보고" in text or "보고서" in text else 0.0)
        row.append(1.0 if "코드" in text or "API" in text or "Python" in text else 0.0)
        row.append(1.0 if "고객" in text or "문의" in text or "FAQ" in text else 0.0)
        row.append(1.0 if "데이터" in text or "지표" in text or "분석" in text else 0.0)
        rows.append(row)
    return np.array(rows, dtype=np.float32)


def embed_texts(texts: list[str]) -> tuple[np.ndarray, str]:
    azure_vectors = embed_texts_azure(texts, required_flag="USE_LLM_TASK_CLASSIFICATION")
    if azure_vectors is not None and azure_vectors.size > 0:
        return azure_vectors, "azure_embedding"
    return embed_texts_rule_fallback(texts), "rule_embedding"


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
    embedding_method: str,
) -> dict[int, tuple[str, float]]:
    anchor_labels, anchor_text_list = _anchor_texts()
    anchor_vectors, anchor_method = embed_texts(anchor_text_list)

    cluster_label_map: dict[int, tuple[str, float]] = {}
    for cluster_id in range(n_clusters):
        member_vectors = vectors[cluster_ids == cluster_id]
        if len(member_vectors) == 0:
            cluster_label_map[cluster_id] = ("SEARCH_QA", 0.0)
            continue

        centroid = member_vectors.mean(axis=0, keepdims=True)
        if centroid.shape[1] != anchor_vectors.shape[1] or embedding_method != anchor_method:
            cluster_label_map[cluster_id] = ("SEARCH_QA", 0.30)
            continue

        similarities = cosine_similarity(centroid, anchor_vectors)[0]
        best_index = int(np.argmax(similarities))
        best_label = anchor_labels[best_index]
        best_score = float(similarities[best_index])
        cluster_label_map[cluster_id] = (best_label, round(max(0.0, min(best_score, 1.0)), 4))
    return cluster_label_map


def _ensure_category_coverage(
    cluster_label_map: dict[int, tuple[str, float]],
    n_clusters: int,
) -> dict[int, tuple[str, float]]:
    if n_clusters != 6:
        return cluster_label_map

    used: set[str] = set()
    duplicated: list[int] = []
    for cluster_id in sorted(cluster_label_map):
        category, _ = cluster_label_map[cluster_id]
        if category in used:
            duplicated.append(cluster_id)
        else:
            used.add(category)

    missing = [category for category in TASK_CATEGORIES if category not in used]
    for cluster_id, category in zip(duplicated, missing):
        _, old_conf = cluster_label_map[cluster_id]
        cluster_label_map[cluster_id] = (category, min(old_conf, 0.60))
    return cluster_label_map


def cluster_tasks(
    masked_texts: list[str],
    n_clusters: int = 6,
    force_six_demo_labels: bool = True,
) -> list[ClusterResult]:
    if not masked_texts:
        return []

    if len(masked_texts) < n_clusters:
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

    vectors, embedding_method = embed_texts(masked_texts)
    model = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
    cluster_ids = model.fit_predict(vectors)

    cluster_label_map = _label_clusters_by_anchor_similarity(vectors, cluster_ids, n_clusters, embedding_method)
    if force_six_demo_labels:
        cluster_label_map = _ensure_category_coverage(cluster_label_map, n_clusters)

    return [
        ClusterResult(
            text=text,
            cluster_id=int(cluster_id),
            category=cluster_label_map[int(cluster_id)][0],
            confidence=cluster_label_map[int(cluster_id)][1],
            method=f"{embedding_method}_kmeans",
        )
        for text, cluster_id in zip(masked_texts, cluster_ids)
    ]


RULES = [
    ("CODE_GENERATION", ["코드", "API", "FastAPI", "React", "Django", "Node.js", "SQLAlchemy", "Python", "버그", "에러", "단위 테스트", "구현", "파싱"]),
    ("CUSTOMER_SUPPORT", ["고객 문의", "상담", "FAQ", "환불", "배송", "결제 오류", "불만 고객", "후속 안내", "정중한 답변", "공감형 안내", "[CUSTOMER_INFO]", "[EMAIL]", "안내", "확인해줘"]),
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
    return CategoryResult(best, round(min(0.55 + score * 0.08, 0.90), 4), "rule_fallback")


def classify_task(masked_text: str) -> CategoryResult:
    if not masked_text:
        return CategoryResult("SEARCH_QA", 0.30, "empty_fallback")

    labels, anchor_text_list = _anchor_texts()
    text_vector, text_method = embed_texts([masked_text])
    anchor_vectors, anchor_method = embed_texts(anchor_text_list)

    if text_vector.shape[1] != anchor_vectors.shape[1] or text_method != anchor_method:
        return classify_rule_fallback(masked_text)

    similarities = cosine_similarity(text_vector, anchor_vectors)[0]
    best_index = int(np.argmax(similarities))
    best_category = labels[best_index]
    best_score = float(similarities[best_index])

    return CategoryResult(
        category=best_category,
        confidence=round(max(0.0, min(best_score, 1.0)), 4),
        method=f"{text_method}_anchor",
    )
