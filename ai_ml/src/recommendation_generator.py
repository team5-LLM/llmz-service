"""ClusterProfile 기반 자동화 추천 카드 생성."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from ai_ml.common import azure_chat_client, bool_setting, chat_deployment, get_setting, int_setting


@dataclass(frozen=True)
class RecommendationCard:
    department: str
    sub_cluster_id: str
    recommendation_title: str
    automation_candidate_type: str
    macro_category: str
    opportunity_score: int
    risk_score: float
    decision: str
    summary: str
    expected_effect: list[str]
    security_guardrails: list[str]
    implementation_difficulty: str
    priority_reason: str
    source_cluster_label: str
    method: str

    def to_dict(self) -> dict:
        return asdict(self)


def _decision(avg_risk_score: float) -> str:
    if avg_risk_score >= 80:
        return "보안 검토 필요"
    if avg_risk_score >= 60:
        return "제한적 도입 권장"
    return "우선 도입 후보"


def _difficulty(macro_category: str, avg_risk_score: float) -> str:
    if avg_risk_score >= 80:
        return "High"
    if macro_category in {"CUSTOMER_SUPPORT", "SEARCH_QA", "REPORT_WRITING"}:
        return "Low"
    if macro_category in {"DOCUMENT_SUMMARY", "DATA_ANALYSIS", "CODE_GENERATION"}:
        return "Medium"
    return "Medium"


def _candidate_type(macro_category: str) -> str:
    return {
        "REPORT_WRITING": "REPORT_AUTOMATION",
        "CODE_GENERATION": "DEV_COPILOT",
        "CUSTOMER_SUPPORT": "FAQ_AGENT",
        "DOCUMENT_SUMMARY": "RAG_SUMMARY_AGENT",
        "DATA_ANALYSIS": "BI_ANALYSIS_AGENT",
        "SEARCH_QA": "KNOWLEDGE_SEARCH_AGENT",
    }.get(macro_category, "AI_WORKFLOW_AUTOMATION")


def calculate_opportunity_score(profile: dict) -> int:
    log_count = int(profile.get("log_count", 0) or 0)
    user_count = int(profile.get("user_count", 0) or 0)
    total_cost = float(profile.get("total_cost", 0.0) or 0.0)
    repeat_ratio = float(profile.get("repeat_ratio", 0.0) or 0.0)

    frequency_score = min(log_count / 50, 1.0) * 35
    repeat_score = min(repeat_ratio, 1.0) * 30
    cost_score = min(total_cost / 1500, 1.0) * 20
    multi_user_score = min(user_count / 8, 1.0) * 15

    score = frequency_score + repeat_score + cost_score + multi_user_score
    return int(round(min(score, 100)))


def _fallback_card(profile: dict) -> RecommendationCard:
    department = str(profile.get("department", "UNKNOWN"))
    sub_cluster_id = str(profile.get("sub_cluster_id", "UNKNOWN_CLUSTER"))
    macro_category = str(profile.get("macro_category", "SEARCH_QA"))
    cluster_label = str(profile.get("cluster_label", "AI 업무 자동화"))
    avg_risk = float(profile.get("avg_risk_score", 0.0) or 0.0)

    title_map = {
        "REPORT_WRITING": f"{department} - {cluster_label} 자동 생성기",
        "CODE_GENERATION": f"{department} - {cluster_label} 지원 Copilot",
        "CUSTOMER_SUPPORT": f"{department} - {cluster_label} Agent",
        "DOCUMENT_SUMMARY": f"{department} - {cluster_label} 요약 Agent",
        "DATA_ANALYSIS": f"{department} - {cluster_label} 분석 Agent",
        "SEARCH_QA": f"{department} - {cluster_label} 지식검색 Agent",
    }
    title = title_map.get(macro_category, f"{department} - {cluster_label} 자동화")

    return RecommendationCard(
        department=department,
        sub_cluster_id=sub_cluster_id,
        recommendation_title=title,
        automation_candidate_type=_candidate_type(macro_category),
        macro_category=macro_category,
        opportunity_score=calculate_opportunity_score(profile),
        risk_score=avg_risk,
        decision=_decision(avg_risk),
        summary=f"{department}에서 반복적으로 나타나는 '{cluster_label}' 업무를 AI 자동화 후보로 추천합니다.",
        expected_effect=[
            "반복 프롬프트 작성 시간 절감",
            "부서 내 유사 업무 처리 방식 표준화",
            "업무 유형별 자동화 후보 우선순위 도출",
        ],
        security_guardrails=[
            "원문 프롬프트 미저장",
            "민감정보 자동 마스킹 후 분석",
            "High/Critical 위험 프롬프트는 관리자 검토 대상으로 분리",
        ],
        implementation_difficulty=_difficulty(macro_category, avg_risk),
        priority_reason=(
            f"로그 {profile.get('log_count', 0)}건, 사용자 {profile.get('user_count', 0)}명, "
            f"반복성 {profile.get('repeat_ratio', 0)} 기준으로 자동화 기회가 확인되었습니다."
        ),
        source_cluster_label=cluster_label,
        method="rule",
    )


def _llm_card(profile: dict) -> RecommendationCard | None:
    if not bool_setting("USE_LLM_RECOMMENDATION", default=False):
        return None

    client = azure_chat_client(required_flag="USE_LLM_RECOMMENDATION")
    deployment = chat_deployment("AZURE_OPENAI_RECOMMENDATION_DEPLOYMENT", "AZURE_OPENAI_DEPLOYMENT")
    if client is None or not deployment:
        return None

    system = """
당신은 기업 LLM 사용 패턴 분석 기반 AI 업무 자동화 컨설턴트입니다.
입력은 모두 마스킹된 프롬프트와 집계 통계입니다. 원문 개인정보나 회사 기밀은 포함되어 있지 않습니다.
클러스터 정보를 바탕으로 자동화 추천 카드를 생성하세요. 추천은 구체적이어야 합니다.
반드시 JSON object만 응답하세요.
형식: {"recommendation_title":"배송 지연/결제 문의 자동 응대 Agent","automation_candidate_type":"FAQ_AGENT","summary":"...","expected_effect":["..."],"security_guardrails":["..."],"implementation_difficulty":"Low","priority_reason":"..."}
"""
    safe_payload = {
        "department": profile.get("department"),
        "sub_cluster_id": profile.get("sub_cluster_id"),
        "macro_category": profile.get("macro_category"),
        "cluster_label": profile.get("cluster_label"),
        "cluster_summary": profile.get("cluster_summary"),
        "representative_masked_prompts": profile.get("representative_masked_prompts", [])[:5],
        "stats": {
            "log_count": profile.get("log_count"),
            "user_count": profile.get("user_count"),
            "total_cost": profile.get("total_cost"),
            "total_tokens": profile.get("total_tokens"),
            "avg_risk_score": profile.get("avg_risk_score"),
            "high_risk_ratio": profile.get("high_risk_ratio"),
            "repeat_ratio": profile.get("repeat_ratio"),
        },
    }

    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(safe_payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=int_setting("AZURE_OPENAI_MAX_OUTPUT_TOKENS", 400),
        )
        data = json.loads(response.choices[0].message.content)
        avg_risk = float(profile.get("avg_risk_score", 0.0) or 0.0)
        title = str(data.get("recommendation_title", "")).strip()
        if not title:
            return None

        return RecommendationCard(
            department=str(profile.get("department", "UNKNOWN")),
            sub_cluster_id=str(profile.get("sub_cluster_id", "UNKNOWN_CLUSTER")),
            recommendation_title=title,
            automation_candidate_type=str(data.get("automation_candidate_type") or _candidate_type(str(profile.get("macro_category", "SEARCH_QA")))),
            macro_category=str(profile.get("macro_category", "SEARCH_QA")),
            opportunity_score=calculate_opportunity_score(profile),
            risk_score=avg_risk,
            decision=_decision(avg_risk),
            summary=str(data.get("summary", "")),
            expected_effect=list(data.get("expected_effect", []))[:5],
            security_guardrails=list(data.get("security_guardrails", []))[:5],
            implementation_difficulty=str(data.get("implementation_difficulty") or _difficulty(str(profile.get("macro_category", "SEARCH_QA")), avg_risk)),
            priority_reason=str(data.get("priority_reason", "")),
            source_cluster_label=str(profile.get("cluster_label", "")),
            method="llm",
        )
    except Exception:
        return None


def generate_recommendation_cards(
    cluster_profiles: list[dict],
    max_cards: int = 5,
    use_llm: bool = True,
) -> list[dict]:
    cards: list[RecommendationCard] = []
    sorted_profiles = sorted(
        cluster_profiles,
        key=lambda p: (int(p.get("log_count", 0) or 0), float(p.get("total_cost", 0.0) or 0.0), int(p.get("user_count", 0) or 0)),
        reverse=True,
    )

    for profile in sorted_profiles:
        if len(cards) >= max_cards:
            break
        card = _llm_card(profile) if use_llm else None
        if card is None:
            card = _fallback_card(profile)
        cards.append(card)
    return [card.to_dict() for card in cards]
