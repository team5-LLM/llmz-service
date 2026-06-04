"""탐지 span을 타입별 마스킹 토큰으로 치환."""
from __future__ import annotations

from ai_ml.pii_schema import SensitiveSpan
from ai_ml.span_utils import merge_overlapping_spans

MASK_TOKEN_BY_TYPE = {
    "EMAIL": "[EMAIL]",
    "PHONE": "[PHONE]",
    "RRN": "[RRN]",
    "CARD": "[CARD]",
    "BUSINESS_REG_NO": "[BUSINESS_REG_NO]",
    "OPENAI_API_KEY": "[API_KEY]",
    "AWS_ACCESS_KEY": "[API_KEY]",
    "SAMPLE_API_KEY": "[API_KEY]",
    "BEARER_TOKEN": "[TOKEN]",
    "JWT": "[TOKEN]",
    "DB_CONNECTION_STRING": "[DB_CONNECTION_STRING]",
    "PASSWORD_ASSIGNMENT": "[SECRET]",
    "CUSTOMER_INFO": "[CUSTOMER_INFO]",
    "VENDOR_INFO": "[VENDOR_INFO]",
    "MONEY_AMOUNT": "[MONEY_AMOUNT]",
    "FINANCIAL_KEYWORD": "[FINANCIAL_INFO]",
    "CONTRACT_INFO": "[CONTRACT_INFO]",
    "INTERNAL_MEETING": "[INTERNAL_MEETING]",
    "INTERNAL_CONFIDENTIAL": "[INTERNAL_CONFIDENTIAL]",
    "HR_SENSITIVE": "[HR_SENSITIVE]",
    "SOURCE_CODE": "[SOURCE_CODE]",
    "PERSON_NAME": "[PERSON_NAME]",
    "COMPANY_CONFIDENTIAL": "[COMPANY_CONFIDENTIAL]",
    "INTERNAL_PROJECT": "[INTERNAL_PROJECT]",
    "FINANCIAL_INFO": "[FINANCIAL_INFO]",
    "LEGAL_REVIEW": "[LEGAL_REVIEW]",
    "SOURCE_CODE_SECRET": "[SOURCE_CODE_SECRET]",
}


def mask_text(text: str, spans: list[SensitiveSpan]) -> str:
    accepted_spans = merge_overlapping_spans(spans)
    masked = text
    for span in sorted(accepted_spans, key=lambda x: x.start, reverse=True):
        token = MASK_TOKEN_BY_TYPE.get(span.type, f"[{span.type}]")
        masked = masked[: span.start] + token + masked[span.end :]
    return masked


def detected_types(spans: list[SensitiveSpan]) -> list[str]:
    return sorted({span.type for span in spans})
