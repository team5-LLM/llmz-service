"""Span 정규화, 병합, confidence 분리 유틸."""
from __future__ import annotations

from dataclasses import is_dataclass
from typing import Any

from ai_ml.pii_schema import SensitiveSpan


def normalize_span(span: Any) -> SensitiveSpan:
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
    normalized = normalize_spans(spans)
    if not normalized:
        return []

    sorted_spans = sorted(normalized, key=lambda s: (s.start, -s.confidence, -(s.end - s.start)))
    merged: list[SensitiveSpan] = []

    for span in sorted_spans:
        if not merged or span.start >= merged[-1].end:
            merged.append(span)
            continue

        last = merged[-1]
        span_len = span.end - span.start
        last_len = last.end - last.start
        should_replace = span.confidence > last.confidence or (
            span.confidence == last.confidence and span_len > last_len
        )
        if should_replace:
            merged[-1] = span

    return merged


def split_by_confidence(spans: list[SensitiveSpan], threshold: float) -> tuple[list[SensitiveSpan], list[SensitiveSpan]]:
    accepted = [span for span in spans if span.confidence >= threshold]
    low_confidence = [span for span in spans if span.confidence < threshold]
    return accepted, low_confidence


def detected_types(spans: list[SensitiveSpan]) -> list[str]:
    return sorted({span.type for span in spans})


def min_confidence(spans: list[SensitiveSpan]) -> float | None:
    if not spans:
        return None
    return min(span.confidence for span in spans)


def spans_to_dicts(spans: list[SensitiveSpan]) -> list[dict]:
    return [span.to_dict() for span in spans]


def llm_entities_to_spans(text: str, entities: list[dict]) -> list[SensitiveSpan]:
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
