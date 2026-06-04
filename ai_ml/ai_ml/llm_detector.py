"""Azure OpenAI 기반 PII/기밀정보 2차 문맥 탐지."""
from __future__ import annotations

import json

from ai_ml.common import azure_chat_client, chat_deployment
from ai_ml.pii_schema import SensitiveSpan

SYSTEM_PROMPT = """
당신은 한국어 회사 LLM 사용 로그에서 개인정보/기밀정보를 탐지하는 보안 분류기입니다.
탐지 대상: PERSON_NAME, CUSTOMER_INFO, VENDOR_INFO, CONTRACT_INFO, COMPANY_CONFIDENTIAL, INTERNAL_PROJECT, HR_SENSITIVE, FINANCIAL_INFO, LEGAL_REVIEW, SOURCE_CODE_SECRET
반드시 JSON object만 응답하세요.
형식: {"entities":[{"type":"CONTRACT_INFO","text":"계약서 초안","confidence":0.91}]}
탐지 결과가 없으면 {"entities":[]} 로 응답하세요.
"""


def detect_llm(text: str) -> list[dict]:
    client = azure_chat_client(required_flag="USE_LLM_PII_DETECTION")
    deployment = chat_deployment("AZURE_OPENAI_DEPLOYMENT")

    if client is None or not deployment:
        return []

    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=600,
        )
        payload = json.loads(response.choices[0].message.content)
        entities = payload.get("entities", [])
        return entities if isinstance(entities, list) else []
    except Exception:
        return []


def entities_to_spans(text: str, entities: list[dict]) -> list[SensitiveSpan]:
    spans: list[SensitiveSpan] = []
    for entity in entities:
        value = str(entity.get("text", "")).strip()
        if not value:
            continue
        start = text.find(value)
        if start < 0:
            continue
        spans.append(
            SensitiveSpan(
                type=str(entity.get("type", "LLM_ENTITY")),
                start=start,
                end=start + len(value),
                text=value,
                confidence=float(entity.get("confidence", 0.0)),
                source="llm",
            )
        )
    return spans
