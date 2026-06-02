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
