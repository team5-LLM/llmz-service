"""AI/ML detected_sensitive_types → prompt_logs Risk 플래그 어댑터."""

from __future__ import annotations

from typing import Iterable

PII_TYPES = frozenset({
    "EMAIL",
    "PHONE",
    "RRN",
    "CARD",
    "BUSINESS_REG_NO",
    "PERSON_NAME",
})

CUSTOMER_TYPES = frozenset({
    "CUSTOMER_INFO",
    "VENDOR_INFO",
})

CONFIDENTIAL_TYPES = frozenset({
    "INTERNAL_CONFIDENTIAL",
    "COMPANY_CONFIDENTIAL",
    "INTERNAL_PROJECT",
    "INTERNAL_MEETING",
    "CONTRACT_INFO",
})

FINANCIAL_TYPES = frozenset({
    "FINANCIAL_KEYWORD",
    "FINANCIAL_INFO",
    "MONEY_AMOUNT",
})

LEGAL_TYPES = frozenset({
    "LEGAL_REVIEW",
})

SECRET_TYPES = frozenset({
    "OPENAI_API_KEY",
    "AWS_ACCESS_KEY",
    "SAMPLE_API_KEY",
    "BEARER_TOKEN",
    "JWT",
    "DB_CONNECTION_STRING",
    "PASSWORD_ASSIGNMENT",
    "SOURCE_CODE_SECRET",
    "SOURCE_CODE",
})

HR_TYPES = frozenset({
    "HR_SENSITIVE",
})


def _normalize_types(detected_sensitive_types: Iterable | None) -> set[str]:
    return {
        str(item).strip().upper()
        for item in (detected_sensitive_types or [])
        if item is not None and str(item).strip()
    }


def sensitive_types_to_flags(
    detected_sensitive_types: Iterable | None,
    *,
    masking_status: str | None = None,
) -> dict[str, bool]:
    """
    AI/ML privacy 결과를 prompt_logs 8개 Risk 플래그로 변환.

    996c658 masking.py 의 Risk breakdown 계약과 risk_service.py 호환.
    """
    types = _normalize_types(detected_sensitive_types)

    pii_detected = bool(types & PII_TYPES)
    customer_detected = bool(types & CUSTOMER_TYPES)
    confidential_detected = bool(types & CONFIDENTIAL_TYPES)
    financial_detected = bool(types & FINANCIAL_TYPES)
    legal_detected = bool(types & LEGAL_TYPES)
    secret_detected = bool(types & SECRET_TYPES)
    hr_detected = bool(types & HR_TYPES)

    exposure_detected = any(
        (
            pii_detected,
            customer_detected,
            confidential_detected,
            financial_detected,
            legal_detected,
            secret_detected,
            hr_detected,
            bool(types),
            masking_status == "MASKED",
        )
    )

    return {
        "pii_detected": pii_detected,
        "customer_detected": customer_detected,
        "confidential_detected": confidential_detected,
        "financial_detected": financial_detected,
        "legal_detected": legal_detected,
        "secret_detected": secret_detected,
        "hr_detected": hr_detected,
        "exposure_detected": exposure_detected,
    }
