"""
SCR-RISK-001 · SCR-RISK-003 — 위험도 overview / levels API 서비스.
"""

from __future__ import annotations

from typing import List

from app.schemas.dashboard import DepartmentStatItem
from app.schemas.risk import DepartmentRiskItem, RiskLevelDefinition
from app.services import dashboard_service as dashboard_svc
from app.utils.date_range import DateRange

RISK_LEVEL_DEFINITIONS: List[RiskLevelDefinition] = [
    RiskLevelDefinition(
        level="Low",
        score_range="0~30",
        meaning="일반 업무 프롬프트",
        recommended_action="기본 마스킹 정책 적용 후 자동화 우선 후보로 검토",
    ),
    RiskLevelDefinition(
        level="Medium",
        score_range="31~60",
        meaning="일부 민감정보 가능성",
        recommended_action="마스킹 정책 적용, 접근 권한 제한",
    ),
    RiskLevelDefinition(
        level="High",
        score_range="61~80",
        meaning="개인정보/기밀 가능성 높음",
        recommended_action="Private 환경 검토, 보관 기간 단축",
    ),
    RiskLevelDefinition(
        level="Critical",
        score_range="81~100",
        meaning="원문 저장 금지, 관리자 검토 필요",
        recommended_action="즉시 도입 보류, 보안 검토 + 감사 로그 적용",
    ),
]


def _to_risk_item(stat: DepartmentStatItem) -> DepartmentRiskItem:
    return DepartmentRiskItem(
        department=stat.department,
        avg_risk_score=stat.avg_risk_score,
        risk_level=stat.risk_level,  # type: ignore[arg-type]
    )


def get_risk_levels() -> dict:
    """정적 등급 정의."""
    return {"levels": [item.model_dump() for item in RISK_LEVEL_DEFINITIONS]}


def get_risk_overview(date_range: DateRange) -> dict:
    """
    기간 내 department_stats 기준 등급별 부서 수 · Critical/High 목록.
    get_dashboard_departments() 재사용.
    """
    stats = dashboard_svc.get_dashboard_departments(date_range)

    summary = {
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "total_departments": len(stats),
    }
    critical: List[DepartmentRiskItem] = []
    high: List[DepartmentRiskItem] = []

    for stat in stats:
        level = stat.risk_level
        if level == "Critical":
            summary["critical_count"] += 1
            critical.append(_to_risk_item(stat))
        elif level == "High":
            summary["high_count"] += 1
            high.append(_to_risk_item(stat))
        elif level == "Medium":
            summary["medium_count"] += 1
        elif level == "Low":
            summary["low_count"] += 1

    critical.sort(key=lambda item: (-item.avg_risk_score, item.department))
    high.sort(key=lambda item: (-item.avg_risk_score, item.department))

    return {
        "period": {
            "from_date": date_range.from_date,
            "to_date": date_range.to_date,
        },
        "summary": summary,
        "critical_departments": [item.model_dump() for item in critical],
        "high_departments": [item.model_dump() for item in high],
    }
