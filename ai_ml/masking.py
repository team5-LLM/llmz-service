"""
[3.2 / FUNC-PROC-002]
masking.py
- PII/기밀정보 마스킹
- 탐지된 span을 [EMAIL], [API_KEY] 등으로 마스킹
- 겹치는 span은 confidence 높은 것으로 우선 마스킹 (confidence 같으면 긴 span 우선)
- 마스킹된 텍스트와 탐지된 entity type 목록 반환
- 향후 LLM 탐지(@llm_detector.py)과 함께 통합되어 최종 PII 후보 선정 및 마스킹에 활용
"""

from app.services.regex_detector import Span

MASK_TOKEN_BY_TYPE = {
    'EMAIL': '[EMAIL]', 'PHONE': '[PHONE]', 'RRN': '[RRN]', 'CARD': '[CARD]', 'BUSINESS_REG_NO': '[BUSINESS_REG_NO]',
    'OPENAI_API_KEY': '[API_KEY]', 'AWS_ACCESS_KEY': '[API_KEY]', 'SAMPLE_API_KEY': '[API_KEY]',
    'BEARER_TOKEN': '[TOKEN]', 'JWT': '[TOKEN]', 'DB_CONNECTION_STRING': '[DB_CONNECTION_STRING]', 'PASSWORD_ASSIGNMENT': '[SECRET]',
    'CUSTOMER_INFO': '[CUSTOMER_INFO]', 'VENDOR_INFO': '[VENDOR_INFO]', 'MONEY_AMOUNT': '[MONEY_AMOUNT]', 'FINANCIAL_KEYWORD': '[FINANCIAL_INFO]',
    'CONTRACT_INFO': '[CONTRACT_INFO]', 'INTERNAL_MEETING': '[INTERNAL_MEETING]', 'INTERNAL_CONFIDENTIAL': '[INTERNAL_CONFIDENTIAL]',
    'HR_SENSITIVE': '[HR_SENSITIVE]', 'SOURCE_CODE': '[SOURCE_CODE]', 'PERSON_NAME': '[PERSON_NAME]', 'COMPANY_CONFIDENTIAL': '[COMPANY_CONFIDENTIAL]',
    'INTERNAL_PROJECT': '[INTERNAL_PROJECT]', 'FINANCIAL_INFO': '[FINANCIAL_INFO]', 'LEGAL_REVIEW': '[LEGAL_REVIEW]', 'SOURCE_CODE_SECRET': '[SOURCE_CODE_SECRET]',
}


def merge_overlapping_spans(spans: list[Span]) -> list[Span]:
    if not spans:
        return []
    spans = sorted(spans, key=lambda s: (s.start, -s.confidence, -(s.end - s.start)))
    merged: list[Span] = []
    for s in spans:
        if not merged or s.start >= merged[-1].end:
            merged.append(s)
            continue
        last = merged[-1]
        if s.confidence > last.confidence or (s.confidence == last.confidence and (s.end - s.start) > (last.end - last.start)):
            merged[-1] = s
    return merged


def mask_text(text: str, spans: list[Span]) -> str:
    masked = text
    for s in sorted(spans, key=lambda x: x.start, reverse=True):
        token = MASK_TOKEN_BY_TYPE.get(s.type, f'[{s.type}]')
        masked = masked[:s.start] + token + masked[s.end:]
    return masked


def detected_types(spans: list[Span]) -> list[str]:
    return sorted({s.type for s in spans})
