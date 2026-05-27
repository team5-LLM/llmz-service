import json
from pathlib import Path

MAPPING_PATH = Path(__file__).resolve().parents[1] / "data" / "automation_mapping.json"


def load_automation_mapping() -> dict:
    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def match_automation_candidate(task_label: str) -> dict:
    """FUNC-PROC-008 자동화 후보 매칭."""
    mapping = load_automation_mapping()

    if task_label not in mapping:
        return mapping.get("기타", {
            "service_name": "업무 자동화 후보 미정",
            "expected_effect": "추가 분석이 필요합니다.",
            "difficulty": "중",
            "required_resources": ["Azure OpenAI"],
        })

    return mapping[task_label]


def build_reason(
    department: str,
    task_label: str,
    task_ratio: float,
    user_count: int,
    avg_risk: float,
    total_cost: float,
) -> list[str]:
    reasons = [
        f"{department}에서 '{task_label}' 업무 비중이 {task_ratio:.1f}%로 나타났습니다.",
        f"해당 업무유형을 사용한 사용자 수는 {user_count}명입니다.",
        f"해당 업무유형의 총 가상 비용은 {total_cost:.2f}입니다.",
    ]

    if avg_risk <= 30:
        reasons.append("평균 Risk Score가 Low 수준이므로 우선 자동화 후보로 검토할 수 있습니다.")
    elif avg_risk <= 60:
        reasons.append("평균 Risk Score가 Medium 수준이므로 기본 마스킹 정책 적용 후 검토할 수 있습니다.")
    else:
        reasons.append("평균 Risk Score가 높아 자동화 전에 보안 검토가 필요합니다.")

    return reasons


def build_recommendation_detail(recommendation: dict) -> dict:
    """SCR-RECO-002 추천 상세 보기 API에서 사용할 상세 정보 생성."""
    return {
        "department": recommendation["department"],
        "task_label": recommendation["task_label"],
        "service_name": recommendation["service_name"],
        "expected_effect": recommendation["expected_effect"],
        "difficulty": recommendation["difficulty"],
        "required_resources": recommendation["required_resources"],
        "opportunity_score": recommendation["opportunity_score"],
        "risk_score": recommendation["risk_score"],
        "risk_level": recommendation["risk_level"],
        "decision": recommendation["decision"],
        "decision_level": recommendation.get("decision_level"),
        "decision_message": recommendation.get("decision_message"),
        "required_action": recommendation.get("required_action"),
        "reason": recommendation["reason"],
        "implementation_guide": build_implementation_guide(recommendation),
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
