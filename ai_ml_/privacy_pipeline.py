"""
[3.1 / FUNC-PROC-001]
[3.2 / FUNC-PROC-002]
[3.3 / FUNC-PROC-003]
[3.9 / FUNC-PROC-009]
[3.10 / FUNC-PROC-010]
[3.4 / FUNC-PROC-004]
[3.5 / FUNC-PROC-005]
[3.8 / FUNC-PROC-008]
[5.3 / SCR-RECO-003]

privacy_pipeline.py

기능:
- AI/ML 파트의 메인 파이프라인
- row 단위 프라이버시 처리:
  process_prompt_privacy(prompt_text, log_id)
- batch 단위 세부 군집화 및 추천 생성:
  generate_cluster_based_recommendations(processed_rows)

row 단위 처리:
1. 정규식 기반 PII/기밀정보 탐지
2. Azure OpenAI 기반 LLM 탐지 (optional)
3. span 병합 및 confidence threshold 적용
4. low confidence span 존재 시 unmasked_rejected 처리
5. accepted span 마스킹
6. 상위 6개 업무 유형 분류
7. 원문 prompt_text 미저장 검증
8. PrivacyProcessResult 반환

batch 단위 처리:
1. masked_text embedding 생성
2. department 내부 sub-clustering
3. cluster profile 생성
4. 자동화 추천 카드 생성

관련 기능명세서:
- 3.1 / FUNC-PROC-001: PII/기밀정보 탐지
- 3.2 / FUNC-PROC-002: 프롬프트 마스킹
- 3.3 / FUNC-PROC-003: 업무 유형 분류
- 3.4 / FUNC-PROC-004: Embedding 생성
- 3.5 / FUNC-PROC-005: Sub-Clustering
- 3.8 / FUNC-PROC-008: 자동화 후보 매칭
- 3.9 / FUNC-PROC-009: 원문 즉시 폐기 검증
- 3.10 / FUNC-PROC-010: 마스킹 실패 Fallback
- 5.3 / SCR-RECO-003: 추천 근거 설명

설치 패키지:
- numpy
- scikit-learn
- openai (optional)
"""

from __future__ import annotations

import gc
import os
from typing import Optional

from ai_ml.pii_schema import CategoryResult, PrivacyProcessResult, SensitiveSpan
from ai_ml.span_utils import (
    detected_types,
    llm_entities_to_spans,
    merge_overlapping_spans,
    min_confidence,
    normalize_spans,
    split_by_confidence,
)


DEFAULT_MASKING_CONFIDENCE_THRESHOLD = 0.80


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _detect_regex(prompt_text: str) -> list[SensitiveSpan]:
    """
    ai_ml/regex_detector.py의 detect_regex를 호출합니다.
    """

    from ai_ml.regex_detector import detect_regex

    return normalize_spans(detect_regex(prompt_text))


def _detect_llm_optional(prompt_text: str) -> list[SensitiveSpan]:
    """
    Azure OpenAI 기반 2차 탐지.

    현재는 USE_AZURE_OPENAI=false면 빈 리스트를 반환합니다.
    llm_detector.py가 아직 완성되지 않았거나 환경변수가 없으면 자동 fallback합니다.
    """

    use_azure = _env_bool("USE_AZURE_OPENAI", default=False)

    if not use_azure:
        return []

    try:
        from ai_ml.llm_detector import detect_llm

        entities = detect_llm(prompt_text)
        if not isinstance(entities, list):
            return []

        return llm_entities_to_spans(prompt_text, entities)

    except Exception:
        # 운영에서는 logger.warning으로 남기는 것을 권장.
        # 지금은 Azure 후순위라 실패해도 정규식-only로 계속 진행.
        return []


def _mask_text(prompt_text: str, spans: list[SensitiveSpan]) -> str:
    """
    ai_ml/masking.py의 mask_text를 호출합니다.
    """

    from ai_ml.masking import mask_text

    return mask_text(prompt_text, spans)


def _classify_task(masked_text: str) -> CategoryResult:
    """
    ai_ml/task_classifier.py의 classify_task를 호출하고
    반환 타입을 CategoryResult로 통일합니다.
    """

    try:
        from ai_ml.task_classifier import classify_task

        result = classify_task(masked_text)

        if isinstance(result, CategoryResult):
            return result

        if isinstance(result, str):
            return CategoryResult(
                category=result,
                confidence=0.50,
                method="rule",
            )

        if isinstance(result, dict):
            return CategoryResult(
                category=str(result.get("category", "SEARCH_QA")),
                confidence=float(result.get("confidence", 0.50)),
                method=str(result.get("method", "rule")),
            )

        # dataclass/object fallback
        return CategoryResult(
            category=str(getattr(result, "category", "SEARCH_QA")),
            confidence=float(getattr(result, "confidence", 0.50)),
            method=str(getattr(result, "method", "rule")),
        )

    except Exception:
        # 분류기가 실패해도 전체 업로드가 죽지 않도록 fallback
        return CategoryResult(
            category="SEARCH_QA",
            confidence=0.30,
            method="fallback",
        )


def _verify_original_disposal(persisted_payload: dict) -> tuple[bool, str]:
    """
    FUNC-PROC-009: 마스킹 후 원문 즉시 폐기 검증.

    Python 메모리에서 문자열이 완전히 사라졌음을 100% 증명할 수는 없습니다.
    대신 아래를 검증합니다.

    1. DB 저장용 payload에 prompt_text 필드가 없음
    2. raw_prompt/original_prompt 같은 원문 필드가 없음
    3. GC 호출로 임시 객체 회수 유도
    """

    forbidden_keys = {
        "prompt_text",
        "raw_prompt",
        "original_prompt",
        "unmasked_prompt",
    }

    for key in forbidden_keys:
        if key in persisted_payload:
            return False, f"FAILED_{key.upper()}_FIELD_PRESENT"

    gc.collect()

    return True, "PASSED_NO_RAW_PROMPT_FIELD_IN_PERSISTED_PAYLOAD"

def _sanitize_spans_for_output(spans: list[SensitiveSpan]) -> list[SensitiveSpan]:
    """
    외부 반환/DB 저장용 span.

    원문 prompt_text는 저장하지 않아도, detected_spans.text 안에
    이메일/API Key/전화번호 같은 민감 문자열 조각이 남을 수 있으므로
    span.text도 반드시 마스킹 토큰으로 치환한다.
    """

    return [
        SensitiveSpan(
            type=span.type,
            start=span.start,
            end=span.end,
            text=f"[{span.type}]",
            confidence=span.confidence,
            source=span.source,
        )
        for span in spans
    ]

def process_prompt_privacy(
    prompt_text: str,
    log_id: Optional[str] = None,
    threshold: Optional[float] = None,
    reject_on_low_confidence: Optional[bool] = None,
    store_masked_text: Optional[bool] = None,
) -> PrivacyProcessResult:
    """
    AI/ML 프라이버시 처리 메인 함수.

    이 함수 하나를 backend/app/services/analysis_pipeline.py에서 호출하면 됩니다.

    처리 흐름:
    3.1 PII/기밀정보 탐지
      - 정규식 1차
      - LLM 2차 optional

    3.2 프롬프트 마스킹
      - span 기반 치환

    3.3 업무 유형 분류
      - 6-class 분류
      - Azure OpenAI optional
      - rule fallback

    3.9 원문 즉시 폐기 검증
      - 저장 payload에 원문 필드가 없는지 확인

    3.10 마스킹 실패 Fallback
      - confidence 임계값 미만 span 존재 시 분석 제외
    """

    if threshold is None:
        threshold = _env_float(
            "MASKING_CONFIDENCE_THRESHOLD",
            DEFAULT_MASKING_CONFIDENCE_THRESHOLD,
        )

    if reject_on_low_confidence is None:
        reject_on_low_confidence = _env_bool(
            "REJECT_ON_LOW_CONFIDENCE",
            default=True,
        )

    if store_masked_text is None:
        store_masked_text = _env_bool(
            "STORE_MASKED_TEXT",
            default=True,
        )

    # 3.1 정규식 + LLM 탐지
    regex_spans = _detect_regex(prompt_text)
    llm_spans = _detect_llm_optional(prompt_text)

    merged_spans = merge_overlapping_spans(regex_spans + llm_spans)

    accepted_spans, low_confidence_spans = split_by_confidence(
        merged_spans,
        threshold,
    )

    all_detected_types = detected_types(merged_spans)

    # 3.10 Fallback: confidence 낮은 민감정보가 있으면 원문 저장 없이 reject
    if reject_on_low_confidence and low_confidence_spans:
        persisted_payload = {
            "masked_text": None,
            "category": None,
            "detected_sensitive_types": all_detected_types,
            "masking_status": "REJECTED_LOW_CONFIDENCE",
        }

        original_disposed, disposal_verification = _verify_original_disposal(
            persisted_payload
        )

        return PrivacyProcessResult(
            log_id=log_id,
            masked_text=None,
            detected_spans=_sanitize_spans_for_output(merged_spans),
            detected_sensitive_types=all_detected_types,
            masking_status="REJECTED_LOW_CONFIDENCE",
            masking_min_confidence=min_confidence(merged_spans),
            category=None,
            category_confidence=None,
            category_method="none",
            original_disposed=original_disposed,
            disposal_verification=disposal_verification,
            unmasked_rejected=True,
            reject_reason="LOW_CONFIDENCE_ENTITY_DETECTED",
        )

    # 3.2 마스킹
    masked_text = _mask_text(prompt_text, accepted_spans)

    masking_status = "MASKED" if accepted_spans else "NO_SENSITIVE_FOUND"

    # 3.3 업무 유형 분류
    category_result = _classify_task(masked_text)

    stored_masked_text = masked_text if store_masked_text else None

    # 3.9 원문 폐기 검증용 저장 payload
    persisted_payload = {
        "masked_text": stored_masked_text,
        "category": category_result.category,
        "detected_sensitive_types": detected_types(accepted_spans),
        "masking_status": masking_status,
    }

    original_disposed, disposal_verification = _verify_original_disposal(
        persisted_payload
    )

    # prompt_text는 반환하지 않음
    return PrivacyProcessResult(
        log_id=log_id,
        masked_text=stored_masked_text,
        detected_spans=_sanitize_spans_for_output(accepted_spans),
        detected_sensitive_types=detected_types(accepted_spans),
        masking_status=masking_status,
        masking_min_confidence=min_confidence(accepted_spans),
        category=category_result.category,
        category_confidence=category_result.confidence,
        category_method=category_result.method,
        original_disposed=original_disposed,
        disposal_verification=disposal_verification,
        unmasked_rejected=False,
        reject_reason="",
    )

def generate_cluster_based_recommendations(
    processed_rows: list[dict],
    group_by_department: bool = True,
    n_clusters: int | None = None,
    max_clusters_per_group: int = 8,
    max_cards: int | None = None,
) -> dict:
    """
    마스킹/상위 업무유형 분류가 끝난 processed_rows를 받아
    sub-clustering → cluster label → recommendation card까지 생성합니다.
    """

    from ai_ml.embedding_clusterer import cluster_processed_logs
    from ai_ml.cluster_labeler import build_cluster_profiles
    from ai_ml.recommendation_generator import generate_recommendation_cards

    if max_cards is None:
        max_cards = int(os.getenv("MAX_LLM_RECOMMENDATION_CARDS", "5"))

    use_llm_label = _env_bool("USE_LLM_CLUSTER_LABEL", default=False)
    use_llm_recommendation = _env_bool("USE_LLM_RECOMMENDATION", default=False)

    clustered_rows = cluster_processed_logs(
        processed_rows=processed_rows,
        group_by_department=group_by_department,
        n_clusters=n_clusters,
        max_clusters_per_group=max_clusters_per_group,
    )

    cluster_profiles = build_cluster_profiles(
        clustered_rows=clustered_rows,
        max_examples=5,
        use_llm_label=use_llm_label,
    )

    recommendation_cards = generate_recommendation_cards(
        cluster_profiles=cluster_profiles,
        max_cards=max_cards,
        use_llm=use_llm_recommendation,
    )

    return {
        "clustered_rows": clustered_rows,
        "cluster_profiles": cluster_profiles,
        "recommendation_cards": recommendation_cards,
    }