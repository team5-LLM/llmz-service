"""SCR-DASH-001 — 대시보드 API 응답 스키마."""

from typing import List

from pydantic import BaseModel

from app.models.upload_history import UploadSummary


class DashboardPeriod(BaseModel):
    from_date: str
    to_date: str


class DashboardSummaryResponse(BaseModel):
    """GET /api/dashboard/summary — §3.2"""

    period: DashboardPeriod
    summary: UploadSummary


class TaskDistributionItem(BaseModel):
    label: str
    count: int
    ratio: float  # dashboard API: 0~1


class DepartmentStatItem(BaseModel):
    """§6.2 — FE types.ts DepartmentStat 와 동일."""

    department: str
    total_requests: int
    total_tokens: int
    total_cost: float
    user_count: int
    avg_risk_score: float
    risk_level: str
    high_critical_ratio: float
    task_distribution: List[TaskDistributionItem]


class DashboardDepartmentsResponse(BaseModel):
    """GET /api/dashboard/departments — §3.3"""

    period: DashboardPeriod
    department_stats: List[DepartmentStatItem]


class DepartmentOverviewItem(BaseModel):
    """§3.4 overview — DepartmentStat 축약."""

    total_requests: int
    total_tokens: int
    total_cost: float
    user_count: int
    avg_risk_score: float
    risk_level: str


class TrendPoint(BaseModel):
    """§6.11 — 시계열 추이 bucket."""

    bucket: str
    requests: int
    tokens: int
    cost: float
    users: int


class TaskPriorityItem(BaseModel):
    """§6.12 — 업무유형 우선순위 (ratio는 0~100 %)."""

    task_label: str
    count: int
    ratio: float
    opportunity_score: int
    risk_score: float
    risk_level: str


class DashboardDepartmentDetailResponse(BaseModel):
    """GET /api/dashboard/departments/{department} — §3.4"""

    department: str
    period: DashboardPeriod
    overview: DepartmentOverviewItem
    trend: List[TrendPoint]
    tasks_by_priority: List[TaskPriorityItem]
