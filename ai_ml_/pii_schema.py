"""
[공통 Schema]

pii_schema.py

기능:
- AI/ML 파이프라인에서 사용하는 공통 dataclass 정의
- SensitiveSpan: PII/기밀정보 탐지 span
- CategoryResult: 상위 업무 유형 분류 결과
- PrivacyProcessResult: row 단위 프라이버시 처리 결과
- 원문 prompt_text는 이 schema에 포함하지 않음

관련 기능명세서:
- 3.1 / FUNC-PROC-001: PII/기밀정보 탐지 결과 표현
- 3.2 / FUNC-PROC-002: 마스킹 결과 표현
- 3.3 / FUNC-PROC-003: 업무 유형 분류 결과 표현
- 3.9 / FUNC-PROC-009: 원문 폐기 검증 결과 표현
- 3.10 / FUNC-PROC-010: 마스킹 실패 fallback 결과 표현
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass(frozen=True)
class SensitiveSpan:
    """
    [PII/기밀정보 탐지 결과 span]
    start/end는 원문 prompt_text 기준 character offset입니다.
    """

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
    """
    [업무 유형 분류 결과]
    category는 6개 업무 유형 중 하나입니다.
    """

    category: str
    confidence: float
    method: str = "rule"  # rule | llm


@dataclass(frozen=True)
class PrivacyProcessResult:
    """
    [AI/ML 프라이버시 처리 파이프라인 결과]
    이 객체에는 원문 prompt_text를 넣지 않습니다.
    """

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