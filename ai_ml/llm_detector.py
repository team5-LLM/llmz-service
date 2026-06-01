"""
# (2차는 옵션)1차로 정규식으로 탐지한 후보들을 LLM 모델로 2차 검증하여 최종 PII/기밀정보 후보 선정 

[3.1 / FUNC-PROC-001] 
llm_detector.py
- PII/기밀정보 탐지 2차 (문맥 기반 탐지)
- Azure OpenAI 모델을 활용한 문맥 기반 탐지 (gpt 4o mini 모델 사용 예정)
- LLM 탐지 결과는 confidence 0.84~0.99로 반환 (모델이 제공하는 confidence 활용)
- 1차로 regex 탐지(@regex_detector.py)와 함께 통합되어 최종 PII 후보 선정에 활용
"""

import json
from app.core.config import settings
from app.services.regex_detector import Span

SYSTEM_PROMPT = """
당신은 한국어 회사 LLM 사용 로그에서 개인정보/기밀정보를 탐지하는 보안 분류기입니다.
탐지 대상: PERSON_NAME, CUSTOMER_INFO, VENDOR_INFO, CONTRACT_INFO, COMPANY_CONFIDENTIAL, INTERNAL_PROJECT, HR_SENSITIVE, FINANCIAL_INFO, LEGAL_REVIEW, SOURCE_CODE_SECRET
반드시 JSON object만 응답하세요.
형식: {"entities":[{"type":"CONTRACT_INFO","text":"계약서 초안","confidence":0.91}]}
탐지 결과가 없으면 {"entities":[]} 로 응답하세요.
"""


def _client():
    if not settings.USE_AZURE_OPENAI:
        return None
    if not settings.AZURE_OPENAI_ENDPOINT or not settings.AZURE_OPENAI_KEY:
        return None
    from openai import AzureOpenAI
    return AzureOpenAI(api_key=settings.AZURE_OPENAI_KEY, api_version=settings.AZURE_OPENAI_API_VERSION, azure_endpoint=settings.AZURE_OPENAI_ENDPOINT)


def detect_llm(text: str) -> list[dict]:
    client = _client()
    if client is None or not settings.AZURE_OPENAI_DEPLOYMENT:
        return []
    resp = client.chat.completions.create(
        model=settings.AZURE_OPENAI_DEPLOYMENT,
        messages=[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': text}],
        response_format={'type': 'json_object'},
        temperature=0,
        max_tokens=600,
    )
    payload = json.loads(resp.choices[0].message.content)
    entities = payload.get('entities', [])
    return entities if isinstance(entities, list) else []


def entities_to_spans(text: str, entities: list[dict]) -> list[Span]:
    spans: list[Span] = []
    for e in entities:
        value = str(e.get('text', '')).strip()
        if not value:
            continue
        start = text.find(value)
        if start < 0:
            continue
        spans.append(Span(str(e.get('type', 'LLM_ENTITY')), start, start + len(value), value, float(e.get('confidence', 0.0)), 'llm'))
    return spans
