"""
[3.2 / FUNC-PROC-002]
masking.py

기능:
- 탐지된 SensitiveSpan을 타입별 마스킹 토큰으로 치환
- EMAIL → [EMAIL]
- PHONE → [PHONE]
- SAMPLE_API_KEY / OPENAI_API_KEY / AWS_ACCESS_KEY → [API_KEY]
- CUSTOMER_INFO → [CUSTOMER_INFO]
- CONTRACT_INFO → [CONTRACT_INFO]
- HR_SENSITIVE → [HR_SENSITIVE]
- FINANCIAL_KEYWORD → [FINANCIAL_INFO]
- 뒤쪽 span부터 치환하여 start/end offset 깨짐 방지

시스템 흐름:
accepted_spans
→ mask_text(prompt_text, accepted_spans)
→ masked_text 생성
→ 원문 prompt_text는 저장하지 않음

관련 기능명세서:
- 3.2 / FUNC-PROC-002: 프롬프트 마스킹
- 3.9 / FUNC-PROC-009: 원문 미저장을 위한 masked_text 생성

주의:
- ai_ml 독립 모듈이므로 import는 app.services가 아니라 ai_ml 기준으로 작성해야 함
  예: from ai_ml.regex_detector import Span
"""

from ai_ml.regex_detector import Span

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
