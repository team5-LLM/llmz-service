def normalize(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0
    return min(value / max_value, 1.0) * 100


def calculate_risk_score(flags: dict) -> int:
    """
    Risk Score =
    개인정보 30% + 기밀정보 25% + 고객정보 20% + 재무/법무 15% + 원문 노출 가능성 10%
    """
    pii_score = 100 if (flags.get("pii_detected") or flags.get("secret_detected")) else 0
    confidential_score = 100 if (flags.get("confidential_detected") or flags.get("hr_detected")) else 0
    customer_score = 100 if flags.get("customer_detected") else 0
    finance_legal_score = 100 if (flags.get("financial_detected") or flags.get("legal_detected")) else 0
    exposure_score = 100 if flags.get("exposure_detected") else 0

    score = (
        pii_score * 0.30
        + confidential_score * 0.25
        + customer_score * 0.20
        + finance_legal_score * 0.15
        + exposure_score * 0.10
    )
    return int(round(score))


def risk_level(score: float) -> str:
    if score <= 30:
        return "Low"
    if score <= 60:
        return "Medium"
    if score <= 80:
        return "High"
    return "Critical"


def difficulty_inverse_score(difficulty: str) -> int:
    return {
        "하": 100,
        "중": 70,
        "중상": 45,
        "상": 25,
    }.get(difficulty, 50)


def calculate_opportunity_score(
    frequency_ratio: float,
    repeat_score: float,
    cost_score: float,
    user_score: float,
    difficulty: str,
) -> int:
    score = (
        frequency_ratio * 0.30
        + repeat_score * 0.25
        + cost_score * 0.20
        + user_score * 0.15
        + difficulty_inverse_score(difficulty) * 0.10
    )
    return int(round(score))


def adoption_decision(opportunity_score: int, risk_score_value: float) -> dict:
    """SCR-RECO-004 Risk 기반 도입 판단 로직."""
    if opportunity_score >= 70 and risk_score_value <= 30:
        return {
            "decision": "우선 추진",
            "decision_level": "recommended",
            "message": "자동화 가치가 높고 보안 위험이 낮아 우선 추진 후보입니다.",
            "required_action": "기본 마스킹 정책 적용 후 PoC 진행",
        }

    if opportunity_score >= 70 and risk_score_value <= 60:
        return {
            "decision": "조건부 추진",
            "decision_level": "conditional",
            "message": "자동화 가치는 높지만 일부 민감정보 가능성이 있어 기본 보안 조치가 필요합니다.",
            "required_action": "마스킹 정책 적용, 접근 권한 제한, 로그 보관 기간 설정",
        }

    if opportunity_score >= 70 and risk_score_value > 60:
        return {
            "decision": "보안 검토 후 추진",
            "decision_level": "security_review",
            "message": "자동화 가치는 높지만 보안 위험도가 높아 즉시 도입보다 보안 검토가 필요합니다.",
            "required_action": "Private 환경 검토, 원문 저장 금지, 권한 통제, 감사 로그 적용",
        }

    if opportunity_score >= 50 and risk_score_value <= 60:
        return {
            "decision": "후순위 검토",
            "decision_level": "later",
            "message": "자동화 가능성은 있으나 우선순위는 높지 않습니다.",
            "required_action": "사용량 증가 여부를 추가 관찰",
        }

    return {
        "decision": "자동화 우선순위 낮음",
        "decision_level": "low_priority",
        "message": "현재 로그 기준으로는 자동화 효과가 제한적입니다.",
        "required_action": "추가 데이터 수집 후 재평가",
    }
