"""
SCR-DASH-001 — 대시보드 집계 서비스 (부서별 LLM 사용 현황)
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.sql import safe_session
from app.models.analysis_result_tables import (
    DepartmentStatRow,
    PromptLogRow,
    RecommendationRow,
)
from app.models.upload_history import UploadStatus, UploadSummary
from app.models.upload_history_table import UploadHistoryRow
from app.schemas.dashboard import (
    DepartmentOverviewItem,
    DepartmentStatItem,
    TaskDistributionItem,
    TaskPriorityItem,
    TrendPoint,
)
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


Granularity = Literal["daily", "weekly", "monthly"]
TaskSort = Literal["priority", "count", "ratio"]

_VALID_GRANULARITIES = frozenset({"daily", "weekly", "monthly"})
_VALID_TASK_SORTS = frozenset({"priority", "count", "ratio"})


def _parse_log_date(created_at: str) -> date | None:
    text = (created_at or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _date_in_range(log_date: date, date_range: DateRange) -> bool:
    start = date.fromisoformat(date_range.from_date)
    end = date.fromisoformat(date_range.to_date)
    return start <= log_date <= end


def _trend_bucket(log_date: date, granularity: Granularity) -> str:
    if granularity == "daily":
        return log_date.isoformat()
    if granularity == "weekly":
        iso = log_date.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return log_date.strftime("%Y-%m")


def _stat_to_overview(stat: DepartmentStatItem) -> DepartmentOverviewItem:
    return DepartmentOverviewItem(
        total_requests=stat.total_requests,
        total_tokens=stat.total_tokens,
        total_cost=stat.total_cost,
        user_count=stat.user_count,
        avg_risk_score=stat.avg_risk_score,
        risk_level=stat.risk_level,
    )


def _build_trend_from_logs(
    logs: List[PromptLogRow],
    date_range: DateRange,
    granularity: Granularity,
) -> List[TrendPoint]:
    buckets: Dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "requests": 0,
            "tokens": 0,
            "cost": 0.0,
            "users": set(),
        }
    )

    for row in logs:
        log_date = _parse_log_date(row.created_at)
        if log_date is None or not _date_in_range(log_date, date_range):
            continue

        bucket = _trend_bucket(log_date, granularity)
        entry = buckets[bucket]
        entry["requests"] += 1
        entry["tokens"] += int(row.total_tokens)
        entry["cost"] += float(row.cost)
        entry["users"].add(row.user_hash)

    return [
        TrendPoint(
            bucket=bucket,
            requests=entry["requests"],
            tokens=entry["tokens"],
            cost=round(entry["cost"], 2),
            users=len(entry["users"]),
        )
        for bucket, entry in sorted(buckets.items())
    ]


def _merge_recommendation_scores(
    rows: List[RecommendationRow],
) -> Dict[str, dict[str, Any]]:
    """task_label별 opportunity(max) · risk(평균용 sum/count) 병합."""
    merged: Dict[str, dict[str, Any]] = {}
    for row in rows:
        label = row.task_label
        if label not in merged:
            merged[label] = {
                "opportunity_score": int(row.opportunity_score),
                "risk_sum": float(row.risk_score),
                "risk_count": 1,
            }
            continue
        item = merged[label]
        item["opportunity_score"] = max(
            item["opportunity_score"],
            int(row.opportunity_score),
        )
        item["risk_sum"] += float(row.risk_score)
        item["risk_count"] += 1
    return merged


def _build_tasks_by_priority(
    logs: List[PromptLogRow],
    recommendations: List[RecommendationRow],
    task_sort: TaskSort,
) -> List[TaskPriorityItem]:
    counts: Dict[str, int] = defaultdict(int)
    risk_from_logs: Dict[str, List[int]] = defaultdict(list)

    for row in logs:
        counts[row.task_label] += 1
        risk_from_logs[row.task_label].append(int(row.risk_score))

    total = sum(counts.values())
    if total == 0:
        return []

    rec_scores = _merge_recommendation_scores(recommendations)
    items: List[TaskPriorityItem] = []

    for task_label, count in counts.items():
        ratio = round(count / total * 100, 1)
        rec = rec_scores.get(task_label)
        if rec is not None:
            avg_risk = rec["risk_sum"] / rec["risk_count"]
            opportunity = rec["opportunity_score"]
        else:
            log_risks = risk_from_logs[task_label]
            avg_risk = sum(log_risks) / len(log_risks) if log_risks else 0.0
            opportunity = 0

        items.append(
            TaskPriorityItem(
                task_label=task_label,
                count=count,
                ratio=ratio,
                opportunity_score=opportunity,
                risk_score=round(avg_risk, 2),
                risk_level=risk_level(avg_risk),
            )
        )

    if task_sort == "count":
        items.sort(key=lambda item: (-item.count, item.task_label))
    elif task_sort == "ratio":
        items.sort(key=lambda item: (-item.ratio, item.task_label))
    else:
        items.sort(
            key=lambda item: (-item.opportunity_score, -item.count, item.task_label)
        )

    return items


def get_dashboard_department_detail(
    department: str,
    date_range: DateRange,
    *,
    granularity: Granularity = "daily",
    task_sort: TaskSort = "priority",
) -> Optional[dict[str, Any]]:
    """
    §3.4 단일 부서 상세 — overview · trend[] · tasks_by_priority[].
    부서 없음 → None (404).
    """
    departments = get_dashboard_departments(date_range)
    stat = next((item for item in departments if item.department == department), None)
    if stat is None:
        return None

    upload_ids = resolve_upload_ids(date_range)
    trend: List[TrendPoint] = []
    tasks: List[TaskPriorityItem] = []

    session = safe_session()
    if session is None:
        logger.warning(
            "SQL 미설정 — %s 상세 trend/tasks 빈 배열 반환",
            department,
        )
    elif upload_ids:
        try:
            log_rows = session.scalars(
                select(PromptLogRow).where(
                    PromptLogRow.upload_id.in_(upload_ids),
                    PromptLogRow.department == department,
                )
            ).all()
            rec_rows = session.scalars(
                select(RecommendationRow).where(
                    RecommendationRow.upload_id.in_(upload_ids),
                    RecommendationRow.department == department,
                )
            ).all()
            trend = _build_trend_from_logs(list(log_rows), date_range, granularity)
            tasks = _build_tasks_by_priority(
                list(log_rows),
                list(rec_rows),
                task_sort,
            )
        except SQLAlchemyError as exc:
            logger.error("get_dashboard_department_detail 실패: %s", exc)
        finally:
            session.close()
    else:
        if session is not None:
            session.close()

    return {
        "department": department,
        "period": {
            "from_date": date_range.from_date,
            "to_date": date_range.to_date,
        },
        "overview": _stat_to_overview(stat),
        "trend": trend,
        "tasks_by_priority": tasks,
    }
