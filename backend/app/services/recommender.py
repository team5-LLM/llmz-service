import json
from pathlib import Path

MAPPING_PATH = Path(__file__).resolve().parents[1] / "data" / "automation_mapping.json"


def load_automation_mapping() -> dict:
    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def match_automation_candidate(task_label: str) -> dict:
    """
    FUNC-PROC-008 자동화 후보 매칭.
    업무유형을 자동화 도구 후보로 변환합니다.
    """
    mapping = load_automation_mapping()
    return mapping.get(task_label, mapping.get("기타"))


def build_reason(
    department: str,
    task_label: str,
    task_ratio: float,
    user_count: int,
    avg_risk: float,
    total_cost: float,
    opportunity_score: int,
) -> list[dict]:
    """
    SCR-RECO-003 추천 근거 설명(XAI).
    수치와 계산 근거를 구조화해서 반환합니다.
    """
    reasons = [
        {
            "factor": "업무유형 비중",
            "value": round(task_ratio, 1),
            "unit": "%",
            "description": f"{department}에서 '{task_label}' 업무 비중이 {task_ratio:.1f}%로 나타났습니다.",
        },
        {
            "factor": "사용자 수",
            "value": user_count,
            "unit": "명",
            "description": f"해당 업무유형을 사용한 사용자 수는 {user_count}명입니다.",
        },
        {
            "factor": "비용 영향",
            "value": round(total_cost, 2),
            "unit": "가상 비용",
            "description": f"해당 업무유형의 총 가상 비용은 {total_cost:.2f}입니다.",
        },
        {
            "factor": "Opportunity Score",
            "value": opportunity_score,
            "unit": "점",
            "description": f"로그 기반 자동화 기회 점수는 {opportunity_score}점입니다.",
        },
    ]

    if avg_risk <= 30:
        risk_description = "평균 Risk Score가 Low 수준이므로 우선 자동화 후보로 검토할 수 있습니다."
    elif avg_risk <= 60:
        risk_description = "평균 Risk Score가 Medium 수준이므로 기본 마스킹 정책 적용 후 검토할 수 있습니다."
    else:
        risk_description = "평균 Risk Score가 높아 자동화 전에 보안 검토가 필요합니다."

    reasons.append({
        "factor": "Risk Score",
        "value": round(avg_risk, 2),
        "unit": "점",
        "description": risk_description,
    })

    return reasons

def build_xai_summary(recommendation: dict) -> str:
    """
    SCR-RECO-003 추천 근거 설명(XAI) 고도화.
    추천 카드의 핵심 판단 근거를 한 문장으로 요약합니다.
    """
    department = recommendation.get("department", "해당 부서")
    task_label = recommendation.get("task_label", "해당 업무")
    opportunity_score = recommendation.get("opportunity_score", 0)
    risk_score = recommendation.get("risk_score", 0)
    risk_level = recommendation.get("risk_level", "Unknown")
    decision_level = recommendation.get("decision_level", "")

    if decision_level == "proceed":
        return (
            f"{department}은 '{task_label}' 업무의 자동화 기회 점수가 "
            f"{opportunity_score}점으로 높고 Risk Level이 {risk_level} 수준이므로 "
            f"우선 도입 후보로 판단됩니다."
        )

    if decision_level == "review":
        return (
            f"{department}은 '{task_label}' 업무의 자동화 가능성이 있으나 "
            f"Risk Score가 {risk_score}점으로 확인되어 마스킹 정책과 보안 검토 후 "
            f"추진 여부를 판단하는 것이 적절합니다."
        )

    if decision_level == "low_priority":
        return (
            f"{department}의 '{task_label}' 업무는 현재 로그 기준 Opportunity Score가 "
            f"{opportunity_score}점으로 높지 않아 우선순위는 낮으며, "
            f"추가 데이터 수집 후 재평가가 필요합니다."
        )

    if risk_level in {"High", "Critical"}:
        return (
            f"{department}의 '{task_label}' 업무는 Risk Level이 {risk_level}로 높아 "
            f"자동화 도입 전 접근 통제와 보안 검토가 우선되어야 합니다."
        )

    return (
        f"{department}의 '{task_label}' 업무는 Opportunity Score {opportunity_score}점, "
        f"Risk Score {risk_score}점을 기준으로 자동화 후보로 산정되었습니다."
    )


def build_key_evidence(recommendation: dict) -> list[str]:
    """
    추천 근거 reason 배열을 프론트에서 바로 표시하기 좋은 문자열 목록으로 변환합니다.
    """
    evidence: list[str] = []

    for reason in recommendation.get("reason", []):
        factor = reason.get("factor")
        value = reason.get("value")
        unit = reason.get("unit", "")

        if factor is None or value is None:
            continue

        evidence.append(f"{factor}: {value}{unit}")

    opportunity_score = recommendation.get("opportunity_score")
    risk_score = recommendation.get("risk_score")
    risk_level = recommendation.get("risk_level")

    if opportunity_score is not None:
        score_text = f"Opportunity Score: {opportunity_score}점"
        if score_text not in evidence:
            evidence.append(score_text)

    if risk_score is not None:
        score_text = f"Risk Score: {risk_score}점"
        if score_text not in evidence:
            evidence.append(score_text)

    if risk_level is not None:
        evidence.append(f"Risk Level: {risk_level}")

    return evidence


def build_decision_reason(recommendation: dict) -> str:
    """
    decision_level과 required_action을 바탕으로 도입 판단 이유를 설명합니다.
    """
    decision = recommendation.get("decision", "검토 필요")
    decision_level = recommendation.get("decision_level", "")
    required_action = recommendation.get("required_action", "추가 검토 필요")

    if decision_level == "proceed":
        return (
            f"{decision}: 자동화 가치가 높고 위험 수준이 낮으므로 "
            f"{required_action}을 진행하는 것이 적절합니다."
        )

    if decision_level == "review":
        return (
            f"{decision}: 자동화 가능성은 있으나 위험 요소가 존재하므로 "
            f"{required_action}이 필요합니다."
        )

    if decision_level == "hold":
        return (
            f"{decision}: 현재 위험 수준이 높아 즉시 도입보다는 "
            f"{required_action}이 우선입니다."
        )

    if decision_level == "low_priority":
        return (
            f"{decision}: 현재 데이터 기준 자동화 효과가 제한적이므로 "
            f"{required_action}이 적절합니다."
        )

    return f"{decision}: {required_action}"


def enrich_recommendation_xai(recommendation: dict) -> dict:
    """
    추천 카드에 XAI 설명 필드를 추가합니다.
    기존 reason 필드는 유지합니다.
    """
    enriched = dict(recommendation)
    enriched["xai_summary"] = build_xai_summary(enriched)
    enriched["key_evidence"] = build_key_evidence(enriched)
    enriched["decision_reason"] = build_decision_reason(enriched)
    return enriched

def build_recommendation_detail(recommendation: dict) -> dict:
    """
    SCR-RECO-002 추천 상세 보기.
    SCR-RECO-003 추천 근거 설명(XAI) 필드 포함.
    """
    enriched = enrich_recommendation_xai(recommendation)

    return {
        "department": enriched["department"],
        "task_label": enriched["task_label"],
        "service_name": enriched["service_name"],
        "expected_effect": enriched["expected_effect"],
        "difficulty": enriched["difficulty"],
        "required_resources": enriched["required_resources"],
        "opportunity_score": enriched["opportunity_score"],
        "risk_score": enriched["risk_score"],
        "risk_level": enriched["risk_level"],
        "decision": enriched["decision"],
        "decision_level": enriched.get("decision_level"),
        "decision_message": enriched.get("decision_message"),
        "required_action": enriched.get("required_action"),
        "reason": enriched["reason"],

        # XAI 고도화 필드
        "xai_summary": enriched["xai_summary"],
        "key_evidence": enriched["key_evidence"],
        "decision_reason": enriched["decision_reason"],

        "implementation_guide": build_implementation_guide(enriched),
    }


def build_implementation_guide(recommendation: dict) -> list[str]:
    task_label = recommendation["task_label"]

    guides = {
        "보고서 작성형": [
            "반복 보고서 양식을 표준 템플릿으로 정의합니다.",
            "CSV, 문서, 회의록 등 입력 데이터를 구조화합니다.",
            "Azure OpenAI를 이용해 보고서 초안을 생성합니다.",
            "생성 결과는 관리자 검토 후 최종 저장합니다.",
        ],
        "코드 생성형": [
            "반복되는 코드 생성/에러 분석 유형을 정의합니다.",
            "소스코드 전체가 아닌 오류 로그와 관련 함수만 입력하도록 제한합니다.",
            "개발 생산성 Copilot 형태로 내부 개발 도구에 연결합니다.",
            "API Key, Secret 등 민감정보 마스킹을 우선 적용합니다.",
        ],
        "고객 응대형": [
            "자주 묻는 질문과 표준 답변을 정리합니다.",
            "고객정보는 마스킹 후 Agent에 전달합니다.",
            "상담/FAQ Agent를 통해 1차 답변 초안을 생성합니다.",
            "High Risk 문의는 상담사 검토 후 발송하도록 제한합니다.",
        ],
        "문서 요약형": [
            "문서를 Blob Storage에 저장하고 검색 가능한 형태로 전처리합니다.",
            "Azure AI Search 또는 RAG 구조를 연결합니다.",
            "문서 원문 접근 권한을 제한합니다.",
            "요약 결과와 참조 문서 위치를 함께 제공합니다.",
        ],
        "데이터 분석형": [
            "분석 대상 지표와 DB 테이블을 정의합니다.",
            "Azure SQL과 연결해 반복 조회 쿼리를 표준화합니다.",
            "BI Agent가 지표 해석과 요약을 생성하도록 구성합니다.",
            "재무 데이터 접근 권한을 제한합니다.",
        ],
        "단순 검색/질문형": [
            "사내 자주 묻는 질문과 문서를 수집합니다.",
            "검색 가능한 지식베이스를 구축합니다.",
            "사내 지식검색 챗봇으로 반복 질의를 줄입니다.",
            "낮은 위험도의 일반 지식부터 우선 적용합니다.",
        ],
    }

    return guides.get(task_label, ["추가 로그 수집 후 자동화 유형을 재분류합니다."])
