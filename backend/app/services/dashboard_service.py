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
from app.utils.task_label_display import task_label_display
from app.services.analysis_pipeline import (
    build_department_stats,
    build_recommendations,
    build_summary_from_dataframe,
)
from app.utils.date_range import DateRange
from app.utils.log_date import parse_log_date

logger = logging.getLogger(__name__)

_COMPLETED = UploadStatus.COMPLETED.value


def prompt_log_row_to_dict(row: PromptLogRow) -> dict[str, Any]:
    """PromptLogRow → analyze/build_* 파이프라인용 dict."""
    return {
        "log_id": int(row.log_id),
        "department": row.department,
        "user_hash": row.user_hash,
        "model": row.model,
        "input_tokens": float(row.input_tokens),
        "output_tokens": float(row.output_tokens),
        "total_tokens": float(row.total_tokens),
        "cost": float(row.cost),
        "created_at": str(row.created_at),
        "masked_prompt": row.masked_prompt,
        "masked_text": row.masked_prompt,
        "task_label": row.task_label,
        "category": row.task_label,
        "risk_score": int(row.risk_score),
        "risk_level": row.risk_level,
        "original_prompt_stored": bool(row.original_prompt_stored),
        "original_discard_verified": bool(row.original_discard_verified),
        "discard_verification_message": row.discard_verification_message,
        "pii_detected": bool(row.pii_detected),
        "customer_detected": bool(row.customer_detected),
        "confidential_detected": bool(row.confidential_detected),
        "financial_detected": bool(row.financial_detected),
        "legal_detected": bool(row.legal_detected),
        "secret_detected": bool(row.secret_detected),
        "hr_detected": bool(row.hr_detected),
        "exposure_detected": bool(row.exposure_detected),
    }


def _latest_completed_upload_id(session) -> Optional[str]:
    """전체 기간 중 가장 최근 completed upload_id."""
    return session.scalar(
        select(UploadHistoryRow.upload_id)
        .where(UploadHistoryRow.status == _COMPLETED)
        .order_by(UploadHistoryRow.uploaded_at.desc())
        .limit(1)
    )


def _query_prompt_logs_in_created_at_range(
    session,
    date_range: DateRange,
    *,
    department: Optional[str] = None,
) -> List[PromptLogRow]:
    completed_ids = select(UploadHistoryRow.upload_id).where(
        UploadHistoryRow.status == _COMPLETED
    )
    query = (
        select(PromptLogRow)
        .where(PromptLogRow.upload_id.in_(completed_ids))
        .where(PromptLogRow.created_at >= date_range.from_date)
        .where(PromptLogRow.created_at < date_range.from_date_exclusive_upper)
    )
    if department is not None:
        query = query.where(PromptLogRow.department == department)
    return list(session.scalars(query).all())


def _query_prompt_logs_for_upload(
    session,
    upload_id: str,
    *,
    department: Optional[str] = None,
) -> List[PromptLogRow]:
    query = select(PromptLogRow).where(PromptLogRow.upload_id == upload_id)
    if department is not None:
        query = query.where(PromptLogRow.department == department)
    return list(session.scalars(query).all())


def _fetch_prompt_logs_strict_created_at(
    date_range: DateRange,
    *,
    department: Optional[str] = None,
) -> List[PromptLogRow]:
    """created_at 기간만 조회 — upload 단위 log fallback 없음 (대시보드 primary용)"""
    session = safe_session()
    if session is None:
        return []

    try:
        return _query_prompt_logs_in_created_at_range(
            session,
            date_range,
            department=department,
        )
    except SQLAlchemyError as exc:
        logger.error("_fetch_prompt_logs_strict_created_at 실패: %s", exc)
        return []
    finally:
        session.close()


def _completed_upload_ids_by_uploaded_at(
    session,
    date_range: DateRange,
) -> List[str]:
    """upload_history.uploaded_at 기간 내 completed upload_id (최신순)."""
    return list(
        session.scalars(
            select(UploadHistoryRow.upload_id)
            .where(UploadHistoryRow.status == _COMPLETED)
            .where(UploadHistoryRow.uploaded_at >= date_range.from_date)
            .where(UploadHistoryRow.uploaded_at < date_range.from_date_exclusive_upper)
            .order_by(UploadHistoryRow.uploaded_at.desc())
        ).all()
    )


def _resolve_snapshot_upload_ids(date_range: DateRange) -> List[str]:
    """
    스냅샷 fallback용 upload_id — uploaded_at 기간 내 completed, 없으면 최신 1건.
    """
    session = safe_session()
    if session is None:
        return []

    try:
        upload_ids = _completed_upload_ids_by_uploaded_at(session, date_range)
        if upload_ids:
            return upload_ids

        fallback_upload_id = _latest_completed_upload_id(session)
        if fallback_upload_id is None:
            return []

        logger.info(
            "스냅샷 fallback — 기간 %s~%s 내 uploaded_at completed 없음, 최신 1건 (upload_id=%s)",
            date_range.from_date,
            date_range.to_date,
            fallback_upload_id,
        )
        return [fallback_upload_id]
    except SQLAlchemyError as exc:
        logger.error("_resolve_snapshot_upload_ids 실패: %s", exc)
        return []
    finally:
        session.close()


def _get_dashboard_summary_from_snapshots(date_range: DateRange) -> UploadSummary:
    """upload_history.summary_json 스냅샷 집계 (hybrid fallback)."""
    upload_ids = _resolve_snapshot_upload_ids(date_range)
    if not upload_ids:
        return UploadSummary()

    session = safe_session()
    if session is None:
        return UploadSummary()

    try:
        rows = session.scalars(
            select(UploadHistoryRow).where(
                UploadHistoryRow.upload_id.in_(upload_ids)
            )
        ).all()
        summaries = [
            parsed
            for row in rows
            if (parsed := _load_summary_json(row.summary_json)) is not None
        ]
        return _merge_summaries(summaries)
    except SQLAlchemyError as exc:
        logger.error("_get_dashboard_summary_from_snapshots 실패: %s", exc)
        return UploadSummary()
    finally:
        session.close()


def _get_dashboard_departments_from_snapshots(
    date_range: DateRange,
) -> List[DepartmentStatItem]:
    """department_stats 테이블 스냅샷 병합 (hybrid fallback)."""
    upload_ids = _resolve_snapshot_upload_ids(date_range)
    if not upload_ids:
        return []

    session = safe_session()
    if session is None:
        return []

    try:
        rows = session.scalars(
            select(DepartmentStatRow).where(
                DepartmentStatRow.upload_id.in_(upload_ids)
            )
        ).all()
        if not rows:
            return []

        merge_inputs = [_row_to_merge_dict(row) for row in rows]
        return _merge_department_stats(merge_inputs)
    except SQLAlchemyError as exc:
        logger.error("_get_dashboard_departments_from_snapshots 실패: %s", exc)
        return []
    finally:
        session.close()


def fetch_prompt_log_rows_in_range(
    date_range: DateRange,
    *,
    department: Optional[str] = None,
) -> List[PromptLogRow]:
    """
    completed 업로드의 prompt_logs 중 created_at 이 기간 내인 행만 반환.
    기간 내 로그가 없으면 빈 배열
    대시보드·Risk·추천·반복패턴 공통 데이터 소스.
    """
    session = safe_session()
    if session is None:
        logger.warning("SQL 미설정 — fetch_prompt_log_rows_in_range 빈 결과")
        return []

    try:
        return _query_prompt_logs_in_created_at_range(
            session,
            date_range,
            department=department,
        )
    except SQLAlchemyError as exc:
        logger.error("fetch_prompt_log_rows_in_range 실패: %s", exc)
        return []
    finally:
        session.close()


def resolve_upload_ids(date_range: DateRange) -> List[str]:
    """
    fetch_prompt_log_rows_in_range 결과에서 upload_id 추출 (중복 제거).
    기간 내 로그 없으면 빈 배열.
    """
    rows = fetch_prompt_log_rows_in_range(date_range)
    seen: set[str] = set()
    ordered: List[str] = []
    for row in rows:
        if row.upload_id in seen:
            continue
        seen.add(row.upload_id)
        ordered.append(row.upload_id)
    return ordered


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
    """KPI 3카드 summary — prompt_logs.created_at 기간 재집계만 사용."""
    rows = _fetch_prompt_logs_strict_created_at(date_range)
    if not rows:
        return UploadSummary()

    import pandas as pd

    log_dicts = [prompt_log_row_to_dict(row) for row in rows]
    summary = build_summary_from_dataframe(pd.DataFrame(log_dicts))
    return UploadSummary.model_validate(summary)


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
            label_display=task_label_display(label),
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


def _department_stat_dicts_to_items(stats: List[dict[str, Any]]) -> List[DepartmentStatItem]:
    items: List[DepartmentStatItem] = []
    for stat in stats:
        task_items = [
            {"label": task.get("label", ""), "count": int(task.get("count", 0))}
            for task in stat.get("task_distribution", [])
        ]
        items.append(
            DepartmentStatItem(
                department=stat["department"],
                total_requests=int(stat["total_requests"]),
                total_tokens=int(stat["total_tokens"]),
                total_cost=float(stat["total_cost"]),
                user_count=int(stat["user_count"]),
                avg_risk_score=float(stat["avg_risk_score"]),
                risk_level=stat["risk_level"],
                high_critical_ratio=float(stat["high_critical_ratio"]),
                task_distribution=_normalize_task_distribution(task_items),
            )
        )
    return items


def get_dashboard_departments(date_range: DateRange) -> List[DepartmentStatItem]:
    """§3.3 department_stats[] — prompt_logs.created_at 기간 재집계만 사용."""
    rows = _fetch_prompt_logs_strict_created_at(date_range)
    if not rows:
        return []

    import pandas as pd

    log_dicts = [prompt_log_row_to_dict(row) for row in rows]
    stats = build_department_stats(pd.DataFrame(log_dicts))
    return _department_stat_dicts_to_items(stats)


Granularity = Literal["daily", "weekly", "monthly"]
TaskSort = Literal["priority", "count", "ratio"]

_VALID_GRANULARITIES = frozenset({"daily", "weekly", "monthly"})
_VALID_TASK_SORTS = frozenset({"priority", "count", "ratio"})


def _parse_log_date(created_at: str) -> date | None:
    return parse_log_date(created_at)


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
                task_label_display=task_label_display(task_label),
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

    trend: List[TrendPoint] = []
    tasks: List[TaskPriorityItem] = []

    log_rows = fetch_prompt_log_rows_in_range(date_range, department=department)
    if log_rows:
        import pandas as pd
        from types import SimpleNamespace

        log_dicts = [prompt_log_row_to_dict(row) for row in log_rows]
        rec_dicts = build_recommendations(pd.DataFrame(log_dicts))
        rec_ns = [
            SimpleNamespace(
                task_label=rec["task_label"],
                opportunity_score=int(rec["opportunity_score"]),
                risk_score=float(rec["risk_score"]),
            )
            for rec in rec_dicts
        ]
        trend = _build_trend_from_logs(list(log_rows), date_range, granularity)
        tasks = _build_tasks_by_priority(list(log_rows), rec_ns, task_sort)

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
