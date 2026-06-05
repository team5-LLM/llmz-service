"""
SCR-RECO — 추천 API 조회 (prompt_logs.created_at 기준).

Read 우선순위 (recommendations 테이블 미사용 — deprecated snapshot):
  1. cluster_recommendations DB (AI/ML cluster 카드)
  2. prompt_logs → build_recommendations() 실시간 task 재집계

XAI: recommender.enrich_recommendation_xai() — ai_ml/xai_explainer 미사용.
"""

from __future__ import annotations

import json
import logging
from typing import Any, List, Optional

import pandas as pd

from app.models.analysis_result_tables import ClusterRecommendationRow
from app.services import dashboard_service as dashboard_svc
from app.services.analysis_pipeline import build_recommendations
from app.services.recommender import cluster_card_to_recommendation, enrich_recommendation_xai
from app.utils.date_range import DateRange

logger = logging.getLogger(__name__)


def _load_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _cluster_row_to_card(row: ClusterRecommendationRow) -> dict[str, Any]:
    return {
        "department": row.department,
        "sub_cluster_id": row.sub_cluster_id,
        "recommendation_title": row.recommendation_title,
        "automation_candidate_type": row.automation_candidate_type,
        "macro_category": row.macro_category,
        "opportunity_score": row.opportunity_score,
        "risk_score": row.risk_score,
        "decision": row.decision,
        "summary": row.summary,
        "expected_effect": _load_json_list(row.expected_effect_json),
        "security_guardrails": _load_json_list(row.security_guardrails_json),
        "implementation_difficulty": row.implementation_difficulty,
        "priority_reason": row.priority_reason,
        "source_cluster_label": row.source_cluster_label,
        "method": row.method,
    }


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


def _merge_cluster_cards(cards: List[dict[str, Any]]) -> List[dict[str, Any]]:
    """동일 (department, sub_cluster_id) — opportunity_score 최대 카드 유지."""
    merged: dict[tuple[str, str], dict[str, Any]] = {}

    for card in cards:
        key = (card["department"], card["sub_cluster_id"])
        existing = merged.get(key)
        if existing is None or card["opportunity_score"] > existing["opportunity_score"]:
            merged[key] = card

    result = list(merged.values())
    result.sort(key=lambda item: item["opportunity_score"], reverse=True)
    return result


def _get_task_based_recommendations(
    date_range: DateRange,
    *,
    department: Optional[str] = None,
) -> List[dict[str, Any]]:
    rows = dashboard_svc.fetch_prompt_log_rows_in_range(
        date_range,
        department=department,
    )
    if not rows:
        return []

    log_dicts = [dashboard_svc.prompt_log_row_to_dict(row) for row in rows]
    recs = build_recommendations(pd.DataFrame(log_dicts))
    merged = _merge_recommendations(recs)
    for item in merged:
        item.setdefault("recommendation_source", "task")
    return merged


def get_recommendations(
    date_range: DateRange,
    *,
    department: Optional[str] = None,
) -> List[dict[str, Any]]:
    """
    기간 내 추천 카드 조회.
    cluster_recommendations DB 우선 → 없으면 prompt_logs task 재집계.
    (legacy recommendations 테이블은 read fallback 없음)
    """
    cluster_rows = dashboard_svc.fetch_cluster_recommendation_rows_in_range(
        date_range,
        department=department,
    )

    if cluster_rows:
        cards = _merge_cluster_cards([_cluster_row_to_card(row) for row in cluster_rows])
        items = [cluster_card_to_recommendation(card) for card in cards]
        return [enrich_recommendation_xai(item) for item in items]

    items = _get_task_based_recommendations(date_range, department=department)
    return [enrich_recommendation_xai(item) for item in items]


def get_recommendation_item(
    department: str,
    task_label: str,
    date_range: DateRange,
) -> Optional[dict[str, Any]]:
    """단일 추천 — cluster(sub_cluster_id) 또는 task_label 기반."""
    cluster_rows = dashboard_svc.fetch_cluster_recommendation_rows_in_range(
        date_range,
        department=department,
    )
    for row in cluster_rows:
        if row.sub_cluster_id == task_label:
            return enrich_recommendation_xai(
                cluster_card_to_recommendation(_cluster_row_to_card(row))
            )

    items = _get_task_based_recommendations(date_range, department=department)
    for item in items:
        if item["task_label"] == task_label:
            return enrich_recommendation_xai(item)
    return None
