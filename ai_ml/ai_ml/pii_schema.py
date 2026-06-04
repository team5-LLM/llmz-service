"""
공통 schema.

중요:
- PrivacyProcessResult에는 원문 prompt_text를 포함하지 않습니다.
- detected_spans.text도 외부 반환 시 [TYPE] 토큰으로 치환합니다.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass(frozen=True)
class SensitiveSpan:
    type: str
    start: int
    end: int
    text: str
    confidence: float
    source: str = "regex"  # regex | llm

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CategoryResult:
    category: str
    confidence: float
    method: str = "rule"  # rule | llm | fallback


@dataclass(frozen=True)
class PrivacyProcessResult:
    log_id: Optional[str]
    masked_text: Optional[str]
    detected_spans: list[SensitiveSpan]
    detected_sensitive_types: list[str]
    masking_status: str
    masking_min_confidence: Optional[float]
    category: Optional[str]
    category_confidence: Optional[float]
    category_method: str
    original_disposed: bool
    disposal_verification: str
    unmasked_rejected: bool
    reject_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "log_id": self.log_id,
            "masked_text": self.masked_text,
            "detected_spans": [span.to_dict() for span in self.detected_spans],
            "detected_sensitive_types": self.detected_sensitive_types,
            "masking_status": self.masking_status,
            "masking_min_confidence": self.masking_min_confidence,
            "category": self.category,
            "category_confidence": self.category_confidence,
            "category_method": self.category_method,
            "original_disposed": self.original_disposed,
            "disposal_verification": self.disposal_verification,
            "unmasked_rejected": self.unmasked_rejected,
            "reject_reason": self.reject_reason,
        }
