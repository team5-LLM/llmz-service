"""
[3.1 / FUNC-PROC-001]
llm_detector.py

기능:
- Azure OpenAI 기반 PII/기밀정보 2차 문맥 탐지
- 정규식으로 잡기 어려운 사람 이름, 계약 문맥, 내부 프로젝트,
  HR 민감정보, 법무 검토, 소스코드 secret 등을 탐지
- 기본 예산 절감을 위해 USE_LLM_PII_DETECTION=false 권장
- privacy_pipeline.py에서 _detect_llm_optional()을 통해 호출되며, 
  Azure 미설정 또는 호출 실패 시 빈 리스트를 반환하여 정규식-only로 fallback

시스템 흐름:
prompt_text
→ detect_llm(prompt_text)
→ span_utils.llm_entities_to_spans()
→ regex span과 병합
→ masking

관련 기능명세서:
- 3.1 / FUNC-PROC-001: 정규식 + LLM 기반 민감정보 탐지

Azure 리소스:
- Azure OpenAI gpt-4o-mini deployment optional

필요 환경변수:
- USE_AZURE_OPENAI
- USE_LLM_PII_DETECTION
- AZURE_OPENAI_ENDPOINT
- AZURE_OPENAI_KEY
- AZURE_OPENAI_DEPLOYMENT
- AZURE_OPENAI_API_VERSION

설치 패키지:
- openai
"""

import json
from app.core.config import settings
from ai_ml.regex_detector import Span

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

    if not getattr(settings, "USE_LLM_PII_DETECTION", False):
        return None

    if not settings.AZURE_OPENAI_ENDPOINT or not settings.AZURE_OPENAI_KEY:
        return None

    from openai import AzureOpenAI

    return AzureOpenAI(
        api_key=settings.AZURE_OPENAI_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    )

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
