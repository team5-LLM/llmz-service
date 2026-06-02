"""
SCR-RISK-001 · SCR-RISK-002 · SCR-RISK-003 — 위험도 API 서비스.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.sql import safe_session
from app.models.analysis_result_tables import PromptLogRow
from app.schemas.dashboard import DepartmentStatItem
from app.schemas.risk import DepartmentRiskItem, RiskLevelDefinition, SensitiveBreakdownItem
from app.services import dashboard_service as dashboard_svc
from app.utils.date_range import DateRange

logger = logging.getLogger(__name__)

SensitivePredicate = Callable[[PromptLogRow], bool]

SENSITIVE_CATEGORIES: List[Tuple[str, str, SensitivePredicate]] = [
    ("personal_info", "개인정보", lambda row: bool(row.pii_detected)),
    ("customer_info", "고객정보", lambda row: bool(row.customer_detected)),
    (
        "confidential",
        "기밀정보",
        lambda row: bool(row.confidential_detected or row.hr_detected),
    ),
    ("source_code", "소스코드", lambda row: bool(row.secret_detected)),
    (
        "finance_legal",
        "재무·법무",
        lambda row: bool(row.financial_detected or row.legal_detected),
    ),
]

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


def _load_department_prompt_logs(
    upload_ids: List[str],
    department: str,
) -> List[PromptLogRow]:
    if not upload_ids:
        return []

    session = safe_session()
    if session is None:
        logger.warning("SQL 미설정 — %s prompt_logs 빈 결과", department)
        return []

    try:
        return list(
            session.scalars(
                select(PromptLogRow).where(
                    PromptLogRow.upload_id.in_(upload_ids),
                    PromptLogRow.department == department,
                )
            ).all()
        )
    except SQLAlchemyError as exc:
        logger.error("prompt_logs 조회 실패 (%s): %s", department, exc)
        return []
    finally:
        session.close()


def build_sensitive_breakdown(logs: List[PromptLogRow]) -> List[SensitiveBreakdownItem]:
    """prompt_logs 마스킹 플래그 → sensitive_breakdown[]"""
    items: List[SensitiveBreakdownItem] = []
    counts: List[int] = []

    for category, label, predicate in SENSITIVE_CATEGORIES:
        count = sum(1 for row in logs if predicate(row))
        counts.append(count)
        items.append(
            SensitiveBreakdownItem(
                category=category,  # type: ignore[arg-type]
                label=label,
                count=count,
                ratio=0.0,
            )
        )

    total_hits = sum(counts)
    if total_hits <= 0:
        return items

    return [
        item.model_copy(
            update={"ratio": round(item.count / total_hits * 100, 1)}
        )
        for item in items
    ]


def get_risk_department_detail(
    department: str,
    date_range: DateRange,
) -> Optional[dict]:
    """
    부서 Risk 점수 + sensitive_breakdown.
    department_stats + prompt_logs 마스킹 플래그 집계
    """
    stats = dashboard_svc.get_dashboard_departments(date_range)
    stat = next((item for item in stats if item.department == department), None)
    if stat is None:
        return None

    upload_ids = dashboard_svc.resolve_upload_ids(date_range)
    logs = _load_department_prompt_logs(upload_ids, department)
    breakdown = build_sensitive_breakdown(logs)

    return {
        "department": department,
        "period": {
            "from_date": date_range.from_date,
            "to_date": date_range.to_date,
        },
        "risk_score": stat.avg_risk_score,
        "risk_level": stat.risk_level,
        "high_critical_ratio": stat.high_critical_ratio,
        "sensitive_breakdown": [item.model_dump() for item in breakdown],
    }
