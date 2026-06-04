"""
FUNC-PROC-008 자동화 후보 매칭 — LLM 기반
부서명 + 업무유형을 Azure OpenAI에 넘겨 부서 맞춤형 service_name / expected_effect 생성.
Azure OpenAI 미설정 시 기존 정적 매핑(automation_mapping.json) 결과를 그대로 반환.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from app.services.scoring import risk_level

_MAPPING_PATH = Path(__file__).resolve().parents[1] / "data" / "automation_mapping.json"

SYSTEM_PROMPT = """당신은 기업 AI 업무 자동화 컨설턴트입니다.
직원들의 LLM 사용 로그를 분석한 결과를 바탕으로,
특정 부서에 가장 적합한 AI 자동화 서비스를 추천합니다.

## 업무유형별 자동화 방향

| 업무유형        | 자동화 유형           | 서비스 예시                          |
|-----------------|----------------------|--------------------------------------|
| 보고서 작성형   | 문서 자동화           | 보고서 자동 생성기, 초안 작성 도우미 |
| 코드 생성형     | 개발 Copilot          | 코드 자동완성 Copilot, 에러 분석 봇  |
| 고객 응대형     | FAQ / 상담 Agent      | 고객 응대 Agent, FAQ 자동 응답 봇    |
| 문서 요약형     | RAG 검색/요약 시스템  | 계약서 요약 봇, 사내 문서 검색 Agent |
| 데이터 분석형   | BI Agent              | 성과 분석 챗봇, 지표 해석 Agent      |
| 단순 검색/질문형 | 사내 지식검색 챗봇   | 사내 지식베이스 Q&A 봇               |

## 출력 규칙

- 반드시 아래 JSON 형식만 출력하세요. 다른 텍스트나 마크다운은 포함하지 마세요.
- service_name: 부서명을 반영한 구체적인 서비스 이름 (예: "마케팅팀 캠페인 보고서 자동 생성기")
- expected_effect: 해당 부서에서 얻을 수 있는 구체적인 기대 효과 1~2문장, 한국어

{"service_name": "...", "expected_effect": "..."}"""

USER_PROMPT_TEMPLATE = """\
다음 분석 결과를 바탕으로 이 부서에 맞는 AI 자동화 서비스를 추천해주세요.

- 부서명: {department}
- 주요 업무유형: {task_label}
- 해당 업무 비중: {task_ratio:.1f}%
- 해당 업무 사용 인원: {user_count}명
- 평균 Risk Score: {avg_risk:.0f} ({risk_level})

service_name에는 반드시 부서명({department})을 반영해 구체적으로 작성하세요.\
"""

RECOMMENDED_PARAMS = {
    "temperature": 0.3,
    "max_tokens": 200,
    "response_format": {"type": "json_object"},
}


def _load_static_mapping() -> dict:
    with open(_MAPPING_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def match_automation_candidate_llm(
    department: str,
    task_label: str,
    task_ratio: float,
    user_count: int,
    avg_risk: float,
) -> dict:
    """
    FUNC-PROC-008 자동화 후보 매칭 (LLM 버전).
    service_name / expected_effect를 부서 맞춤형으로 생성합니다.
    difficulty / required_resources는 기존 정적 매핑에서 유지합니다.
    """
    static = _load_static_mapping()
    base = static.get(task_label, static.get("기타"))

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip()

    if not (endpoint and api_key and deployment):
        return base

    from openai import AzureOpenAI

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version="2024-02-01",
    )

    user_message = USER_PROMPT_TEMPLATE.format(
        department=department,
        task_label=task_label,
        task_ratio=task_ratio,
        user_count=user_count,
        avg_risk=avg_risk,
        risk_level=risk_level(avg_risk),
    )

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        **RECOMMENDED_PARAMS,
    )

    llm_result = json.loads(response.choices[0].message.content)

    return {
        "service_name": llm_result.get("service_name", base["service_name"]),
        "expected_effect": llm_result.get("expected_effect", base["expected_effect"]),
        "difficulty": base["difficulty"],
        "required_resources": base["required_resources"],
    }
