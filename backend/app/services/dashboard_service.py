"""
SCR-DASH-001 — 대시보드 집계 서비스 (부서별 LLM 사용 현황)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.sql import safe_session
from app.models.analysis_result_tables import DepartmentStatRow
from app.models.upload_history import UploadStatus, UploadSummary
from app.models.upload_history_table import UploadHistoryRow
from app.schemas.dashboard import DepartmentStatItem, TaskDistributionItem
from app.services.scoring import risk_level
from app.utils.date_range import DateRange

logger = logging.getLogger(__name__)

_COMPLETED = UploadStatus.COMPLETED.value


def _completed_in_range_query(date_range: DateRange):
    """기간 내 completed 업로드 — uploaded_at 포함 범위 (이력 API와 동일)."""
    return (
        select(UploadHistoryRow.upload_id)
        .where(UploadHistoryRow.status == _COMPLETED)
        .where(UploadHistoryRow.uploaded_at >= date_range.from_date)
        .where(UploadHistoryRow.uploaded_at < date_range.from_date_exclusive_upper)
        .order_by(UploadHistoryRow.uploaded_at.desc())
    )


def _latest_completed_query():
    """전체 기간 중 가장 최근 completed 1건 (fallback)."""
    return (
        select(UploadHistoryRow.upload_id)
        .where(UploadHistoryRow.status == _COMPLETED)
        .order_by(UploadHistoryRow.uploaded_at.desc())
        .limit(1)
    )


def resolve_upload_ids(date_range: DateRange) -> List[str]:
    """
    대시보드 집계 대상 upload_id 목록.

    1. date_range 내 status=completed 인 upload_id (최신순)
    2. 없으면 전체 upload_history 에서 최신 completed 1건
    3. SQL 미설정/오류 → []
    """
    session = safe_session()
    if session is None:
        logger.warning("SQL 미설정 — resolve_upload_ids 빈 결과 반환")
        return []

    try:
        rows = session.scalars(_completed_in_range_query(date_range)).all()
        if rows:
            return list(rows)

        fallback = session.scalar(_latest_completed_query())
        if fallback is not None:
            logger.info(
                "기간 %s~%s 내 completed 없음 — 최신 completed 1건 사용 (upload_id=%s)",
                date_range.from_date,
                date_range.to_date,
                fallback,
            )
            return [fallback]

        return []
    except SQLAlchemyError as exc:
        logger.error("resolve_upload_ids 실패: %s", exc)
        return []
    finally:
        session.close()


def _load_summary_json(raw: str | None) -> UploadSummary | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    try:
        return UploadSummary.model_validate(data)
    except Exception:
        return None


def _merge_summaries(summaries: List[UploadSummary]) -> UploadSummary:
    """선택 upload들의 summary_json 필드 합산 · avg_risk_score는 total_logs 가중 평균."""
    if not summaries:
        return UploadSummary()

    total_logs = sum(item.total_logs for item in summaries)
    total_tokens = sum(item.total_tokens for item in summaries)
    total_cost = sum(item.total_cost for item in summaries)
    departments = sum(item.departments for item in summaries)

    if total_logs > 0:
        weighted_risk = sum(
            item.avg_risk_score * item.total_logs for item in summaries
        ) / total_logs
        avg_risk_score = round(weighted_risk, 2)
    else:
        avg_risk_score = 0.0

    return UploadSummary(
        total_logs=total_logs,
        departments=departments,
        total_tokens=total_tokens,
        total_cost=round(total_cost, 2),
        avg_risk_score=avg_risk_score,
    )


def get_dashboard_summary(date_range: DateRange) -> UploadSummary:
    """
    KPI 3카드 summary — resolve_upload_ids → upload_history.summary_json 집계
    upload 없음 / SQL 미설정 → 0 summary
    """
    upload_ids = resolve_upload_ids(date_range)
    if not upload_ids:
        return UploadSummary()

    session = safe_session()
    if session is None:
        logger.warning("SQL 미설정 — get_dashboard_summary 0 summary 반환")
        return UploadSummary()

    try:
        query = select(UploadHistoryRow).where(
            UploadHistoryRow.upload_id.in_(upload_ids)
        )
        rows = session.scalars(query).all()
        summaries = [
            parsed
            for row in rows
            if (parsed := _load_summary_json(row.summary_json)) is not None
        ]
        return _merge_summaries(summaries)
    except SQLAlchemyError as exc:
        logger.error("get_dashboard_summary 실패: %s", exc)
        return UploadSummary()
    finally:
        session.close()


def _load_task_distribution(raw: str | None) -> List[dict[str, Any]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _normalize_task_distribution(items: List[dict[str, Any]]) -> List[TaskDistributionItem]:
    """label별 count 합산 후 ratio 0~1 재계산."""
    counts: Dict[str, int] = {}
    for item in items:
        label = str(item.get("label", ""))
        if not label:
            continue
        counts[label] = counts.get(label, 0) + int(item.get("count", 0))

    total = sum(counts.values())
    if total == 0:
        return []

    return [
        TaskDistributionItem(
            label=label,
            count=count,
            ratio=round(count / total, 4),
        )
        for label, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    ]


def _row_to_merge_dict(row: DepartmentStatRow) -> dict[str, Any]:
    return {
        "department": row.department,
        "total_requests": int(row.total_requests),
        "total_tokens": int(row.total_tokens),
        "total_cost": float(row.total_cost),
        "user_count": int(row.user_count),
        "avg_risk_score": float(row.avg_risk_score),
        "high_critical_ratio": float(row.high_critical_ratio),
        "task_distribution": _load_task_distribution(row.task_distribution_json),
    }


def _merge_department_stats(rows: List[dict[str, Any]]) -> List[DepartmentStatItem]:
    """동일 department 병합 — count/tokens/cost sum · risk 가중 평균 · task_distribution 재계산."""
    grouped: Dict[str, List[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["department"], []).append(row)

    merged: List[DepartmentStatItem] = []
    for department, items in grouped.items():
        total_requests = sum(item["total_requests"] for item in items)
        total_tokens = sum(item["total_tokens"] for item in items)
        total_cost = sum(item["total_cost"] for item in items)
        user_count = sum(item["user_count"] for item in items)

        if total_requests > 0:
            avg_risk = sum(
                item["avg_risk_score"] * item["total_requests"] for item in items
            ) / total_requests
            high_critical = sum(
                item["total_requests"] * item["high_critical_ratio"] / 100.0
                for item in items
            ) / total_requests * 100.0
        else:
            avg_risk = 0.0
            high_critical = 0.0

        task_items: List[dict[str, Any]] = []
        for item in items:
            for task in item["task_distribution"]:
                task_items.append(
                    {
                        "label": task.get("label", ""),
                        "count": int(task.get("count", 0)),
                    }
                )

        merged.append(
            DepartmentStatItem(
                department=department,
                total_requests=total_requests,
                total_tokens=total_tokens,
                total_cost=round(total_cost, 2),
                user_count=user_count,
                avg_risk_score=round(avg_risk, 2),
                risk_level=risk_level(avg_risk),
                high_critical_ratio=round(high_critical, 1),
                task_distribution=_normalize_task_distribution(task_items),
            )
        )

    merged.sort(key=lambda item: item.total_cost, reverse=True)
    return merged


def get_dashboard_departments(date_range: DateRange) -> List[DepartmentStatItem]:
    """
    §3.3 department_stats[] — resolve_upload_ids → department_stats 테이블 조회·병합.
    upload 없음 / SQL 미설정 → [].
    """
    upload_ids = resolve_upload_ids(date_range)
    if not upload_ids:
        return []

    session = safe_session()
    if session is None:
        logger.warning("SQL 미설정 — get_dashboard_departments 빈 배열 반환")
        return []

    try:
        query = select(DepartmentStatRow).where(
            DepartmentStatRow.upload_id.in_(upload_ids)
        )
        rows = session.scalars(query).all()
        if not rows:
            return []

        merge_inputs = [_row_to_merge_dict(row) for row in rows]
        return _merge_department_stats(merge_inputs)
    except SQLAlchemyError as exc:
        logger.error("get_dashboard_departments 실패: %s", exc)
        return []
    finally:
        session.close()
