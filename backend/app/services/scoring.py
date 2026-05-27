def normalize(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0
    return min(value / max_value, 1.0) * 100

def calculate_risk_score(flags: dict) -> int:
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
    return {"하": 100, "중": 70, "중상": 45, "상": 25}.get(difficulty, 50)

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

def adoption_decision(opportunity_score: int, risk_score_value: float) -> str:
    if opportunity_score >= 70 and risk_score_value <= 60:
        return "우선 추진"
    if opportunity_score >= 70 and risk_score_value > 60:
        return "보안 검토 후 추진"
    if opportunity_score >= 50 and risk_score_value <= 60:
        return "후순위 검토"
    return "자동화 우선순위 낮음"
