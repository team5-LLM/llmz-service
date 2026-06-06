"""AI/ML 영문 category → 한국어 표시 레이어 (내부 키는 영문 유지)."""

from __future__ import annotations

TASK_LABEL_ALIASES: dict[str, str] = {
    "REPORT_WRITING": "보고서 작성형",
    "CODE_GENERATION": "코드 생성형",
    "CUSTOMER_SUPPORT": "고객 응대형",
    "DOCUMENT_SUMMARY": "문서 요약형",
    "DATA_ANALYSIS": "데이터 분석형",
    "SEARCH_QA": "단순 검색/질문형",
}


def normalize_task_label(task_label: str) -> str:
    """영문 AI/ML category를 한국어 업무유형으로 정규화 (가이드·매핑 조회용)."""
    return TASK_LABEL_ALIASES.get(task_label, task_label)


def task_label_display(task_label: str, *, cluster_label: str | None = None) -> str:
    """API·UI 표시용 한국어 라벨. cluster 추천은 cluster_label 우선."""
    if cluster_label:
        return cluster_label
    return normalize_task_label(task_label)
