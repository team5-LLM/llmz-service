"""DEPRECATED — BE 미연동. API XAI는 backend/app/services/recommender.enrich_recommendation_xai() 사용.

(구) LLM 기반 설명 생성기. Azure OpenAI 호출로 reason[]을 자연어 문단으로 변환하나,
운영 API의 xai_summary/key_evidence/decision_reason은 BE 규칙 기반 enrich가 제공합니다.
"""
from __future__ import annotations

from ai_ml.common import azure_chat_client, chat_deployment

_SYSTEM_PROMPT = (
    "당신은 기업 내 LLM 사용 로그를 분석하여 업무 자동화 추천 근거를 설명하는 AI 분석가입니다. "
    "주어진 수치 데이터를 바탕으로 왜 이 부서의 해당 업무유형이 자동화 우선 후보인지 "
    "3문장 이내의 자연스러운 한국어로 설명하세요. "
    "수치를 직접 언급하되 단순 나열이 아닌 인과 관계가 드러나도록 작성하세요."
)


def _build_user_message(department: str, task_label: str, reasons: list[dict]) -> str:
    factor_lines = "\n".join(
        f"- {reason['factor']}: {reason['value']}{reason['unit']} — {reason['description']}"
        for reason in reasons
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
    client = azure_chat_client()
    deployment = chat_deployment("AZURE_OPENAI_DEPLOYMENT")

    if client is None or not deployment:
        return None

    try:
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
    except Exception:
        return None
