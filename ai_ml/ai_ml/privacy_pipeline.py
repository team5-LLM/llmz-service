"""
AI/ML privacy pipeline main orchestration.

Public API:
- process_prompt_privacy(prompt_text, log_id=None, ...)
- generate_cluster_based_recommendations(processed_rows, ...)
"""
from __future__ import annotations

import gc
from typing import Optional

from ai_ml.common import bool_setting, float_setting, int_setting
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


def _detect_regex(prompt_text: str) -> list[SensitiveSpan]:
    from ai_ml.regex_detector import detect_regex

    return normalize_spans(detect_regex(prompt_text))


def _detect_llm_optional(prompt_text: str) -> list[SensitiveSpan]:
    if not bool_setting("USE_AZURE_OPENAI", default=False):
        return []
    if not bool_setting("USE_LLM_PII_DETECTION", default=False):
        return []

    try:
        from ai_ml.llm_detector import detect_llm

        entities = detect_llm(prompt_text)
        if not isinstance(entities, list):
            return []
        return llm_entities_to_spans(prompt_text, entities)
    except Exception:
        return []


def _mask_text(prompt_text: str, spans: list[SensitiveSpan]) -> str:
    from ai_ml.masking import mask_text

    return mask_text(prompt_text, spans)


def _classify_task(masked_text: str) -> CategoryResult:
    try:
        from ai_ml.task_classifier import classify_task

        result = classify_task(masked_text)
        if isinstance(result, CategoryResult):
            return result
        if isinstance(result, str):
            return CategoryResult(category=result, confidence=0.50, method="rule")
        if isinstance(result, dict):
            return CategoryResult(
                category=str(result.get("category", "SEARCH_QA")),
                confidence=float(result.get("confidence", 0.50)),
                method=str(result.get("method", "rule")),
            )
        return CategoryResult(
            category=str(getattr(result, "category", "SEARCH_QA")),
            confidence=float(getattr(result, "confidence", 0.50)),
            method=str(getattr(result, "method", "rule")),
        )
    except Exception:
        return CategoryResult(category="SEARCH_QA", confidence=0.30, method="fallback")


def _verify_original_disposal(persisted_payload: dict) -> tuple[bool, str]:
    """
    원문이 저장 payload에 포함되지 않았는지 검증합니다.
    Python 메모리에서 문자열이 완전히 사라졌음을 100% 증명할 수는 없으므로,
    DB 저장용 payload에 원문 필드가 없는지 검증하는 방식입니다.
    """
    forbidden_keys = {"prompt_text", "raw_prompt", "original_prompt", "unmasked_prompt"}
    for key in forbidden_keys:
        if key in persisted_payload:
            return False, f"FAILED_{key.upper()}_FIELD_PRESENT"

    gc.collect()
    return True, "PASSED_NO_RAW_PROMPT_FIELD_IN_PERSISTED_PAYLOAD"


def _sanitize_spans_for_output(spans: list[SensitiveSpan]) -> list[SensitiveSpan]:
    """
    외부 반환/DB 저장용 span.
    span.text 안에 원문 조각이 남지 않도록 [TYPE] 토큰으로 치환합니다.
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
    if threshold is None:
        threshold = float_setting("MASKING_CONFIDENCE_THRESHOLD", DEFAULT_MASKING_CONFIDENCE_THRESHOLD)

    if reject_on_low_confidence is None:
        reject_on_low_confidence = bool_setting("REJECT_ON_LOW_CONFIDENCE", default=True)

    if store_masked_text is None:
        store_masked_text = bool_setting("STORE_MASKED_TEXT", default=True)

    regex_spans = _detect_regex(prompt_text)
    llm_spans = _detect_llm_optional(prompt_text)
    merged_spans = merge_overlapping_spans(regex_spans + llm_spans)
    accepted_spans, low_confidence_spans = split_by_confidence(merged_spans, threshold)
    all_detected_types = detected_types(merged_spans)

    if reject_on_low_confidence and low_confidence_spans:
        persisted_payload = {
            "masked_text": None,
            "category": None,
            "detected_sensitive_types": all_detected_types,
            "masking_status": "REJECTED_LOW_CONFIDENCE",
        }
        original_disposed, disposal_verification = _verify_original_disposal(persisted_payload)

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

    masked_text = _mask_text(prompt_text, accepted_spans)
    masking_status = "MASKED" if accepted_spans else "NO_SENSITIVE_FOUND"
    category_result = _classify_task(masked_text)
    stored_masked_text = masked_text if store_masked_text else None

    persisted_payload = {
        "masked_text": stored_masked_text,
        "category": category_result.category,
        "detected_sensitive_types": detected_types(accepted_spans),
        "masking_status": masking_status,
    }
    original_disposed, disposal_verification = _verify_original_disposal(persisted_payload)

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
    from ai_ml.cluster_labeler import build_cluster_profiles
    from ai_ml.embedding_clusterer import cluster_processed_logs
    from ai_ml.recommendation_generator import generate_recommendation_cards

    if max_cards is None:
        max_cards = int_setting("MAX_LLM_RECOMMENDATION_CARDS", 5)

    use_llm_label = bool_setting("USE_LLM_CLUSTER_LABEL", default=False)
    use_llm_recommendation = bool_setting("USE_LLM_RECOMMENDATION", default=False)

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
