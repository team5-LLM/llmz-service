""" SCR-RISK-001 · SCR-RISK-003 — 위험도 API 응답 스키마."""

from typing import List, Literal

from pydantic import BaseModel

from app.schemas.dashboard import DashboardPeriod


SensitiveCategory = Literal[
    "personal_info",
    "customer_info",
    "confidential",
    "source_code",
    "finance_legal",
]


class DepartmentRiskItem(BaseModel):
    """Critical/High 부서 요약."""

    department: str
    avg_risk_score: float
    risk_level: Literal["Low", "Medium", "High", "Critical"]


class RiskOverviewSummary(BaseModel):
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    total_departments: int


class RiskOverviewResponse(BaseModel):
    """GET /api/risk/overview"""

    period: DashboardPeriod
    summary: RiskOverviewSummary
    critical_departments: List[DepartmentRiskItem]
    high_departments: List[DepartmentRiskItem]


class RiskLevelDefinition(BaseModel):
    """등급 정의 (툴팁)."""

    level: Literal["Low", "Medium", "High", "Critical"]
    score_range: str
    meaning: str
    recommended_action: str


class RiskLevelsResponse(BaseModel):
    """GET /api/risk/levels"""

    levels: List[RiskLevelDefinition]


class SensitiveBreakdownItem(BaseModel):
    """민감정보 유형별 탐지 비중"""

    category: SensitiveCategory
    label: str
    count: int
    ratio: float


class RiskDepartmentDetailResponse(BaseModel):
    """GET /api/risk/departments/{department}"""

    department: str
    period: DashboardPeriod
    risk_score: float
    risk_level: Literal["Low", "Medium", "High", "Critical"]
    high_critical_ratio: float
    sensitive_breakdown: List[SensitiveBreakdownItem]
