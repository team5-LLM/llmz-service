"""
[3.1 / FUNC-PROC-001, 3.10 / FUNC-PROC-010]
span_utils.py

기능:
- regex_detector.py와 llm_detector.py의 탐지 결과를 SensitiveSpan으로 정규화
- 겹치는 span 병합
- confidence 기준 accepted / low_confidence 분리
- 탐지된 민감정보 type 목록 생성
- LLM entity 결과를 원문 offset 기반 span으로 변환

시스템 흐름:
regex_spans + llm_spans
→ normalize_spans()
→ merge_overlapping_spans()
→ split_by_confidence()
→ accepted_spans는 masking
→ low_confidence_spans는 fallback/reject 판단

관련 기능명세서:
- 3.1 / FUNC-PROC-001: 탐지 결과 병합
- 3.10 / FUNC-PROC-010: confidence 임계값 기반 reject
"""

from __future__ import annotations

from dataclasses import is_dataclass
from typing import Any

from ai_ml.pii_schema import SensitiveSpan


def normalize_span(span: Any) -> SensitiveSpan:
    """
    regex_detector.py나 llm_detector.py에서 반환한 span 객체를
    SensitiveSpan으로 통일합니다.

    지원 형태:
    - SensitiveSpan
    - dataclass with type/start/end/text/confidence/source
    - dict with type/start/end/text/confidence/source
    """

    if isinstance(span, SensitiveSpan):
        return span

    if isinstance(span, dict):
        return SensitiveSpan(
            type=str(span.get("type", "UNKNOWN")),
            start=int(span.get("start", 0)),
            end=int(span.get("end", 0)),
            text=str(span.get("text", "")),
            confidence=float(span.get("confidence", 0.0)),
            source=str(span.get("source", "unknown")),
        )

    if is_dataclass(span):
        return SensitiveSpan(
            type=str(getattr(span, "type")),
            start=int(getattr(span, "start")),
            end=int(getattr(span, "end")),
            text=str(getattr(span, "text")),
            confidence=float(getattr(span, "confidence")),
            source=str(getattr(span, "source", "regex")),
        )

    # 일반 객체 fallback
    return SensitiveSpan(
        type=str(getattr(span, "type", "UNKNOWN")),
        start=int(getattr(span, "start", 0)),
        end=int(getattr(span, "end", 0)),
        text=str(getattr(span, "text", "")),
        confidence=float(getattr(span, "confidence", 0.0)),
        source=str(getattr(span, "source", "unknown")),
    )


def normalize_spans(spans: list[Any]) -> list[SensitiveSpan]:
    return [normalize_span(span) for span in spans]


def merge_overlapping_spans(spans: list[Any]) -> list[SensitiveSpan]:
    """
    겹치는 span 제거.

    우선순위:
    1. confidence 높은 span
    2. confidence 같으면 더 긴 span
    3. 그래도 같으면 먼저 등장한 span
    """

    normalized = normalize_spans(spans)

    if not normalized:
        return []

    sorted_spans = sorted(
        normalized,
        key=lambda s: (s.start, -s.confidence, -(s.end - s.start)),
    )

    merged: list[SensitiveSpan] = []

    for span in sorted_spans:
        if not merged:
            merged.append(span)
            continue

        last = merged[-1]

        # 겹치지 않음
        if span.start >= last.end:
            merged.append(span)
            continue

        # 겹침 → 더 좋은 span 선택
        span_len = span.end - span.start
        last_len = last.end - last.start

        should_replace = (
            span.confidence > last.confidence
            or (
                span.confidence == last.confidence
                and span_len > last_len
            )
        )

        if should_replace:
            merged[-1] = span

    return merged


def split_by_confidence(
    spans: list[SensitiveSpan],
    threshold: float,
) -> tuple[list[SensitiveSpan], list[SensitiveSpan]]:
    """
    confidence 기준으로 accepted / low_confidence 분리.
    """

    accepted = [span for span in spans if span.confidence >= threshold]
    low_confidence = [span for span in spans if span.confidence < threshold]
    return accepted, low_confidence


def detected_types(spans: list[SensitiveSpan]) -> list[str]:
    """
    탐지된 민감정보 type 목록.
    """

    return sorted({span.type for span in spans})


def min_confidence(spans: list[SensitiveSpan]) -> float | None:
    if not spans:
        return None
    return min(span.confidence for span in spans)


def spans_to_dicts(spans: list[SensitiveSpan]) -> list[dict]:
    return [span.to_dict() for span in spans]


def llm_entities_to_spans(text: str, entities: list[dict]) -> list[SensitiveSpan]:
    """
    LLM 탐지 결과를 span으로 변환.

    LLM 결과 예시:
    [
      {"type": "CONTRACT_INFO", "text": "계약서 초안", "confidence": 0.91}
    ]

    LLM 결과에는 위치 정보가 없으므로 text.find()로 start/end를 보강합니다.
    """

    spans: list[SensitiveSpan] = []

    for entity in entities:
        entity_text = str(entity.get("text", "")).strip()
        if not entity_text:
            continue

        start = text.find(entity_text)
        if start < 0:
            continue

        spans.append(
            SensitiveSpan(
                type=str(entity.get("type", "LLM_ENTITY")),
                start=start,
                end=start + len(entity_text),
                text=entity_text,
                confidence=float(entity.get("confidence", 0.0)),
                source="llm",
            )
        )

    return spans