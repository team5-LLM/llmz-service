"""정규식 기반 PII/기밀정보 1차 탐지."""
from __future__ import annotations

import re

from ai_ml.pii_schema import SensitiveSpan

# backward compatibility: 기존 코드에서 Span을 import해도 동작하도록 alias 유지
Span = SensitiveSpan

PATTERNS: dict[str, tuple[str, float]] = {
    "EMAIL": (r"(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}(?![A-Za-z0-9._%+\-])", 0.98),
    "PHONE": (r"(?<![0-9])01[016789][-\s]?\d{3,4}[-\s]?\d{4}(?![0-9])", 0.97),
    "RRN": (r"(?<![0-9])\d{6}[-\s]?[1-4]\d{6}(?![0-9])", 0.98),
    "CARD": (r"(?<![0-9])(?:\d{4}[-\s]?){3}\d{4}(?![0-9])", 0.94),
    "BUSINESS_REG_NO": (r"(?<![0-9])\d{3}[-\s]?\d{2}[-\s]?\d{5}(?![0-9])", 0.90),
    "OPENAI_API_KEY": (r"(?<![A-Za-z0-9_\-])sk-[A-Za-z0-9_\-]{20,}(?![A-Za-z0-9_\-])", 0.99),
    "AWS_ACCESS_KEY": (r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])", 0.99),
    "SAMPLE_API_KEY": (r"(?<![A-Za-z0-9_])API_KEY_SAMPLE_DO_NOT_USE_[A-Za-z0-9_]*(?![A-Za-z0-9_])", 0.99),
    "BEARER_TOKEN": (r"(?<![A-Za-z0-9_])Bearer\s+[A-Za-z0-9._\-]{20,}(?![A-Za-z0-9._\-])", 0.96),
    "JWT": (r"(?<![A-Za-z0-9_\-])eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+(?![A-Za-z0-9_\-])", 0.96),
    "DB_CONNECTION_STRING": (r"(?<![A-Za-z0-9])(?:postgresql|postgres|mysql|mongodb|redis|mssql|sqlserver)://[^\s]+", 0.96),
    "PASSWORD_ASSIGNMENT": (r"(?i)\b(password|passwd|pwd|secret|token)\s*[:=]\s*['\"]?[^'\"\s,;]{6,}", 0.90),
    "CUSTOMER_INFO": (r"(?:가상고객|샘플고객|테스트고객|데모고객)[A-Z0-9]*", 0.90),
    "VENDOR_INFO": (r"(?:거래처|협력사|공급업체|파트너사)\s?[A-Z0-9]*", 0.86),
    "MONEY_AMOUNT": (r"(?<![0-9])\d{1,3}(?:,\d{3})*원|(?<![0-9])\d+원|(?<![0-9])\d+(?:\.\d+)?억", 0.88),
    "FINANCIAL_KEYWORD": (r"(매출|비용|영업이익|순이익|원가|정산|급여|예산|견적|마진|손익)", 0.84),
    "CONTRACT_INFO": (r"(계약서|NDA|비밀유지|위약금|해지 조건|계약 조건|계약 조항|법무 검토|소송 가능성|약관)", 0.88),
    "INTERNAL_MEETING": (r"(내부회의록|내부 회의록|회의록|임원 보고|경영진 보고|비공개 회의)", 0.84),
    "INTERNAL_CONFIDENTIAL": (r"(기밀|대외비|비공개|내부 프로젝트|사업 전략|서비스 로드맵|경쟁사 분석)", 0.86),
    "HR_SENSITIVE": (r"(인사평가|면접 피드백|평가 문구|채용 평가|징계|연봉|급여|지원자 수|입사 초기 이탈률)", 0.88),
    "SOURCE_CODE": (r"(def\s+\w+\(|class\s+\w+\(|import\s+\w+|SELECT\s+.+\s+FROM|CREATE\s+TABLE|console\.log|function\s+\w+\()", 0.86),
}


def detect_regex(text: str) -> list[SensitiveSpan]:
    if not text:
        return []

    spans: list[SensitiveSpan] = []
    for entity_type, (pattern, confidence) in PATTERNS.items():
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            spans.append(
                SensitiveSpan(
                    type=entity_type,
                    start=match.start(),
                    end=match.end(),
                    text=match.group(),
                    confidence=confidence,
                    source="regex",
                )
            )
    return spans
