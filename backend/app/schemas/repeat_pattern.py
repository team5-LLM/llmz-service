"""SCR-DASH-003 — 반복 프롬프트 비율 API 응답 스키마."""

from typing import List, Literal, Optional

from pydantic import BaseModel

from app.schemas.dashboard import DashboardPeriod

AnalysisMethod = Literal["heuristic", "cluster", "mixed"]


class RepeatPatternItem(BaseModel):
    pattern_key: str
    cluster_id: Optional[str] = None
    task_label: str
    label: str
    count: int
    ratio: float
    is_repeat: bool
    sample_masked_prompt: str


class DepartmentRepeatStat(BaseModel):
    department: str
    total_requests: int
    repeat_requests: int
    repeat_ratio: float
    unique_patterns: int
    patterns: List[RepeatPatternItem]


class DashboardRepeatPatternsResponse(BaseModel):
    """GET /api/dashboard/repeat-patterns — §3.5"""

    period: DashboardPeriod
    analysis_method: AnalysisMethod
    min_pattern_count: int
    departments: List[DepartmentRepeatStat]


class DepartmentRepeatPatternsResponse(BaseModel):
    """GET /api/dashboard/departments/{department}/repeat-patterns — §3.5"""

    period: DashboardPeriod
    analysis_method: AnalysisMethod
    min_pattern_count: int
    department: str
    total_requests: int
    repeat_requests: int
    repeat_ratio: float
    unique_patterns: int
    patterns: List[RepeatPatternItem]
