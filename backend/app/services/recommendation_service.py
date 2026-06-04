"""SCR-RECO — recommendations 재집계 (prompt_logs.created_at 기준)."""

from __future__ import annotations
import logging
from typing import Any, List, Optional
import pandas as pd
from app.services import dashboard_service as dashboard_svc
from app.services.analysis_pipeline import build_recommendations
from app.utils.date_range import DateRange
from app.services.recommender import enrich_recommendation_xai

logger = logging.getLogger(__name__)

def _merge_recommendations(items: List[dict[str, Any]]) -> List[dict[str, Any]]:
    """동일 (department, task_label) — opportunity_score 최대 row 유지."""
    merged: dict[tuple[str, str], dict[str, Any]] = {}

    for item in items:
        if item.get("task_label") == "기타":
            continue
        key = (item["department"], item["task_label"])
        existing = merged.get(key)
        if existing is None or item["opportunity_score"] > existing["opportunity_score"]:
            merged[key] = item

    result = list(merged.values())
    result.sort(key=lambda item: item["opportunity_score"], reverse=True)
    return result

def get_recommendations(
    date_range: DateRange,
    *,
    department: Optional[str] = None,
) -> List[dict[str, Any]]:
    """
    기간 내 prompt_logs.created_at 필터 후 build_recommendations() 재집계.
    SQL 미설정 / 해당 기간 로그 없음 → [].
    """
    rows = dashboard_svc.fetch_prompt_log_rows_in_range(
        date_range,
        department=department,
    )

    if not rows:
        return []
    
    log_dicts = [dashboard_svc.prompt_log_row_to_dict(row) for row in rows]
    recs = build_recommendations(pd.DataFrame(log_dicts))
    merged = _merge_recommendations(recs)

    return [enrich_recommendation_xai(item) for item in merged]

def get_recommendation_item(
    department: str,
    task_label: str,
    date_range: DateRange,
) -> Optional[dict[str, Any]]:

    """단일 (department, task_label) 추천 — 없으면 None (404)."""
    items = get_recommendations(date_range, department=department)
    for item in items:
        if item["task_label"] == task_label:
            return item
    return None
