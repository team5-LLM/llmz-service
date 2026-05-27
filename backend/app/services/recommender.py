import json
from pathlib import Path

MAPPING_PATH = Path(__file__).resolve().parents[1] / "data" / "automation_mapping.json"

def load_automation_mapping() -> dict:
    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def build_reason(department: str, task_label: str, task_ratio: float, user_count: int, avg_risk: float, total_cost: float) -> list[str]:
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
