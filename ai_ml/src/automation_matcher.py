"""부서명 + 업무유형 기반 자동화 후보 매칭."""
from __future__ import annotations

import json
from pathlib import Path

from .common import azure_chat_client, chat_deployment, risk_level

_MAPPING_PATH = Path(__file__).resolve().parents[1] / "data" / "automation_mapping.json"

STATIC_AUTOMATION_MAPPING = {
    "보고서 작성형": {
        "service_name": "보고서 자동 생성기",
        "expected_effect": "정기 보고서 초안 작성 시간을 줄이고 보고 품질을 표준화합니다.",
        "difficulty": "Medium",
        "required_resources": ["문서 템플릿", "검수자", "권한 관리"],
    },
    "코드 생성형": {
        "service_name": "개발 Copilot",
        "expected_effect": "반복 코드 작성과 오류 분석 시간을 줄입니다.",
        "difficulty": "Medium",
        "required_resources": ["코드 저장소 연동", "보안 가드레일"],
    },
    "고객 응대형": {
        "service_name": "고객 응대 Agent",
        "expected_effect": "반복 문의 답변 초안 작성 시간을 줄이고 응대 품질을 표준화합니다.",
        "difficulty": "Low",
        "required_resources": ["FAQ", "상담 이력", "검수 플로우"],
    },
    "문서 요약형": {
        "service_name": "문서 요약/RAG Agent",
        "expected_effect": "긴 문서의 핵심 쟁점 파악 시간을 줄입니다.",
        "difficulty": "Medium",
        "required_resources": ["문서 저장소", "검색 인덱스", "권한 관리"],
    },
    "데이터 분석형": {
        "service_name": "BI 분석 Agent",
        "expected_effect": "지표 해석과 인사이트 도출을 자동화합니다.",
        "difficulty": "Medium",
        "required_resources": ["데이터 마트", "지표 정의서"],
    },
    "단순 검색/질문형": {
        "service_name": "사내 지식검색 챗봇",
        "expected_effect": "반복적인 사내 문의 대응 시간을 줄입니다.",
        "difficulty": "Low",
        "required_resources": ["사내 문서", "검색 인덱스"],
    },
    "기타": {
        "service_name": "AI 업무 자동화",
        "expected_effect": "반복 업무를 표준화하고 처리 시간을 줄입니다.",
        "difficulty": "Medium",
        "required_resources": ["업무 정의", "보안 검토"],
    },
}

SYSTEM_PROMPT = """당신은 기업 AI 업무 자동화 컨설턴트입니다.
직원들의 LLM 사용 로그를 분석한 결과를 바탕으로 특정 부서에 가장 적합한 AI 자동화 서비스를 추천합니다.
반드시 아래 JSON 형식만 출력하세요.
{"service_name":"...","expected_effect":"..."}"""

USER_PROMPT_TEMPLATE = """다음 분석 결과를 바탕으로 이 부서에 맞는 AI 자동화 서비스를 추천해주세요.

- 부서명: {department}
- 주요 업무유형: {task_label}
- 해당 업무 비중: {task_ratio:.1f}%
- 해당 업무 사용 인원: {user_count}명
- 평균 Risk Score: {avg_risk:.0f} ({risk_level})

service_name에는 반드시 부서명({department})을 반영해 구체적으로 작성하세요."""


def _load_static_mapping() -> dict:
    if _MAPPING_PATH.exists():
        with open(_MAPPING_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    return {
        "REPORT_WRITING": {
            "service_name": "보고서 자동 생성기",
            "expected_effect": "반복적인 보고서 초안 작성 시간을 줄이고 문서 품질을 표준화합니다.",
            "difficulty": "Medium",
            "required_resources": ["문서 템플릿", "검토 워크플로우"],
        },
        "CODE_GENERATION": {
            "service_name": "개발 Copilot",
            "expected_effect": "반복 코드 작성과 오류 분석 시간을 줄입니다.",
            "difficulty": "Medium",
            "required_resources": ["코드 저장소", "보안 가이드라인"],
        },
        "CUSTOMER_SUPPORT": {
            "service_name": "고객 응대 Agent",
            "expected_effect": "반복 문의 응답 시간을 줄이고 상담 품질을 표준화합니다.",
            "difficulty": "Low",
            "required_resources": ["FAQ", "상담 이력"],
        },
        "DOCUMENT_SUMMARY": {
            "service_name": "문서 요약 Agent",
            "expected_effect": "긴 문서의 핵심 내용을 빠르게 요약합니다.",
            "difficulty": "Medium",
            "required_resources": ["문서 저장소", "RAG 검색 인프라"],
        },
        "DATA_ANALYSIS": {
            "service_name": "BI 분석 Agent",
            "expected_effect": "반복적인 지표 분석과 인사이트 도출을 자동화합니다.",
            "difficulty": "Medium",
            "required_resources": ["정형 데이터", "대시보드 지표"],
        },
        "SEARCH_QA": {
            "service_name": "사내 지식검색 챗봇",
            "expected_effect": "반복적인 사내 지식 검색과 질의응답 시간을 줄입니다.",
            "difficulty": "Low",
            "required_resources": ["사내 문서", "검색 인덱스"],
        },
        "기타": {
            "service_name": "AI 업무 자동화 도우미",
            "expected_effect": "반복 업무를 자동화 후보로 분류하고 개선 기회를 탐색합니다.",
            "difficulty": "Medium",
            "required_resources": ["업무 로그", "운영 정책"],
        },
    }

def match_automation_candidate_llm(
    department: str,
    task_label: str,
    task_ratio: float,
    user_count: int,
    avg_risk: float,
) -> dict:
    static = _load_static_mapping()
    base = static.get(task_label, static.get("기타", STATIC_AUTOMATION_MAPPING["기타"]))

    client = azure_chat_client()
    deployment = chat_deployment("AZURE_OPENAI_DEPLOYMENT")
    if client is None or not deployment:
        return base

    user_message = USER_PROMPT_TEMPLATE.format(
        department=department,
        task_label=task_label,
        task_ratio=task_ratio,
        user_count=user_count,
        avg_risk=avg_risk,
        risk_level=risk_level(avg_risk),
    )

    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        llm_result = json.loads(response.choices[0].message.content)
        return {
            "service_name": llm_result.get("service_name", base["service_name"]),
            "expected_effect": llm_result.get("expected_effect", base["expected_effect"]),
            "difficulty": base["difficulty"],
            "required_resources": base["required_resources"],
        }
    except Exception:
        return base
