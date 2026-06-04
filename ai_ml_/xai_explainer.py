"""
SCR-RECO-003 추천 근거 설명 (XAI)
build_reason()이 만든 구조화 데이터를 Azure OpenAI로 자연어 설명 한 단락으로 변환합니다.
Azure OpenAI 미설정 시 None 반환 → 프론트엔드는 수치 기반 reason 리스트만 표시합니다.
"""

from __future__ import annotations

import os

_SYSTEM_PROMPT = (
    "당신은 기업 내 LLM 사용 로그를 분석하여 업무 자동화 추천 근거를 설명하는 AI 분석가입니다. "
    "주어진 수치 데이터를 바탕으로 왜 이 부서의 해당 업무유형이 자동화 우선 후보인지 "
    "3문장 이내의 자연스러운 한국어로 설명하세요. "
    "수치를 직접 언급하되 단순 나열이 아닌 인과 관계가 드러나도록 작성하세요."
)


def _build_user_message(department: str, task_label: str, reasons: list[dict]) -> str:
    factor_lines = "\n".join(
        f"- {r['factor']}: {r['value']}{r['unit']} — {r['description']}"
        for r in reasons
    )
    return (
        f"부서: {department}\n"
        f"업무유형: {task_label}\n\n"
        f"분석 근거:\n{factor_lines}\n\n"
        "위 데이터를 종합하여 자동화 추천 근거를 설명해주세요."
    )


def generate_xai_explanation(
    reasons: list[dict],
    department: str,
    task_label: str,
) -> str | None:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip()

    if not (endpoint and api_key and deployment):
        return None

    from openai import AzureOpenAI

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version="2024-02-01",
    )

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(department, task_label, reasons)},
        ],
        max_tokens=300,
        temperature=0.3,
    )

    return response.choices[0].message.content.strip()
