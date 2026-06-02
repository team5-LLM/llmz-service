"""
SCR-DASH-003 — 부서별 반복 프롬프트 비율.

현재: masked_prompt 정규화 기반 heuristic 그룹핑.
추후: prompt_logs.cluster_id / pattern_label (FUNC-PROC-005) 연동 시 동일 API 응답 유지.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.sql import safe_session
from app.models.analysis_result_tables import PromptLogRow
from app.services import dashboard_service as dashboard_svc
from app.utils.date_range import DateRange

logger = logging.getLogger(__name__)

AnalysisMethod = Literal["heuristic", "cluster", "mixed"]
MethodQuery = Literal["auto", "heuristic", "cluster"]

_VALID_METHODS = frozenset({"auto", "heuristic", "cluster"})
DEFAULT_MIN_PATTERN_COUNT = 2
_SAMPLE_PROMPT_MAX_LEN = 80


@dataclass(frozen=True)
class PromptLogEntry:
    """분석 입력 — ORM 행 또는 파이프라인 결과를 공통 형태로."""

    department: str
    task_label: str
    masked_prompt: str
    cluster_id: Optional[str] = None
    pattern_label: Optional[str] = None


@dataclass(frozen=True)
class PatternGroup:
    pattern_key: str
    cluster_id: Optional[str]
    task_label: str
    label: str
    count: int
    sample_masked_prompt: str
    source: Literal["heuristic", "cluster"]


def _normalize_prompt(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _truncate(text: str, max_len: int = _SAMPLE_PROMPT_MAX_LEN) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3] + "..."


def _heuristic_pattern_key(task_label: str, normalized_prompt: str) -> str:
    digest = hashlib.sha256(f"{task_label}|{normalized_prompt}".encode()).hexdigest()[:16]
    return f"h-{digest}"


def _cluster_pattern_key(task_label: str, cluster_id: str) -> str:
    digest = hashlib.sha256(f"{task_label}|{cluster_id}".encode()).hexdigest()[:12]
    return f"c-{digest}"


def _group_key_and_label(
    entry: PromptLogEntry,
    *,
    method: MethodQuery,
) -> tuple[str, str, Optional[str], Literal["heuristic", "cluster"]]:
    use_cluster = entry.cluster_id is not None and method in ("auto", "cluster")

    if use_cluster and entry.cluster_id:
        label = entry.pattern_label or f"{entry.task_label} · cluster {entry.cluster_id}"
        return (
            _cluster_pattern_key(entry.task_label, entry.cluster_id),
            label,
            entry.cluster_id,
            "cluster",
        )

    normalized = _normalize_prompt(entry.masked_prompt)
    label = _truncate(entry.masked_prompt) or entry.task_label
    return (
        _heuristic_pattern_key(entry.task_label, normalized),
        label,
        None,
        "heuristic",
    )


def group_prompt_logs(
    logs: List[PromptLogEntry],
    *,
    method: MethodQuery = "auto",
) -> tuple[List[PatternGroup], AnalysisMethod]:
    buckets: Dict[str, dict] = {}

    for entry in logs:
        key, label, cluster_id, source = _group_key_and_label(entry, method=method)
        if key not in buckets:
            buckets[key] = {
                "pattern_key": key,
                "cluster_id": cluster_id,
                "task_label": entry.task_label,
                "label": label,
                "count": 0,
                "sample_masked_prompt": _truncate(entry.masked_prompt),
                "source": source,
            }
        buckets[key]["count"] += 1
        if len(entry.masked_prompt) > len(buckets[key]["sample_masked_prompt"]):
            buckets[key]["sample_masked_prompt"] = _truncate(entry.masked_prompt)

    groups = [
        PatternGroup(
            pattern_key=item["pattern_key"],
            cluster_id=item["cluster_id"],
            task_label=item["task_label"],
            label=item["label"],
            count=item["count"],
            sample_masked_prompt=item["sample_masked_prompt"],
            source=item["source"],
        )
        for item in buckets.values()
    ]
    groups.sort(key=lambda g: (-g.count, g.pattern_key))

    sources = {group.source for group in groups}
    if not sources:
        analysis_method: AnalysisMethod = "heuristic"
    elif sources == {"heuristic"}:
        analysis_method = "heuristic"
    elif sources == {"cluster"}:
        analysis_method = "cluster"
    else:
        analysis_method = "mixed"

    return groups, analysis_method


def summarize_department_patterns(
    department: str,
    groups: List[PatternGroup],
    *,
    min_pattern_count: int,
    total_requests: int,
) -> dict:
    patterns = []
    repeat_requests = 0

    for group in groups:
        ratio = round(group.count / total_requests * 100, 1) if total_requests else 0.0
        is_repeat = group.count >= min_pattern_count
        if is_repeat:
            repeat_requests += group.count
        patterns.append(
            {
                "pattern_key": group.pattern_key,
                "cluster_id": group.cluster_id,
                "task_label": group.task_label,
                "label": group.label,
                "count": group.count,
                "ratio": ratio,
                "is_repeat": is_repeat,
                "sample_masked_prompt": group.sample_masked_prompt,
            }
        )

    repeat_ratio = (
        round(repeat_requests / total_requests * 100, 1) if total_requests else 0.0
    )

    return {
        "department": department,
        "total_requests": total_requests,
        "repeat_requests": repeat_requests,
        "repeat_ratio": repeat_ratio,
        "unique_patterns": len(groups),
        "patterns": patterns,
    }


def _row_to_entry(row: PromptLogRow) -> PromptLogEntry:
    return PromptLogEntry(
        department=row.department,
        task_label=row.task_label,
        masked_prompt=row.masked_prompt,
        cluster_id=getattr(row, "cluster_id", None),
        pattern_label=getattr(row, "pattern_label", None),
    )


def _load_prompt_log_entries(upload_ids: List[str]) -> List[PromptLogEntry]:
    if not upload_ids:
        return []

    session = safe_session()
    if session is None:
        logger.warning("SQL 미설정 — repeat pattern 빈 로그 반환")
        return []

    try:
        rows = session.scalars(
            select(PromptLogRow).where(PromptLogRow.upload_id.in_(upload_ids))
        ).all()
        return [_row_to_entry(row) for row in rows]
    except SQLAlchemyError as exc:
        logger.error("repeat pattern prompt_logs 조회 실패: %s", exc)
        return []
    finally:
        session.close()


def get_repeat_patterns(
    date_range: DateRange,
    *,
    department: Optional[str] = None,
    method: MethodQuery = "auto",
    min_pattern_count: int = DEFAULT_MIN_PATTERN_COUNT,
) -> Optional[dict]:
    """
    부서별 반복 프롬프트 집계.
    department 지정 시 해당 부서만 — 없으면 404 (None).
    """
    if min_pattern_count < 2:
        min_pattern_count = 2

    known_departments = dashboard_svc.get_dashboard_departments(date_range)
    dept_names = {item.department for item in known_departments}

    if department is not None and department not in dept_names:
        return None

    upload_ids = dashboard_svc.resolve_upload_ids(date_range)
    entries = _load_prompt_log_entries(upload_ids)

    by_department: Dict[str, List[PromptLogEntry]] = {}
    for entry in entries:
        if department is not None and entry.department != department:
            continue
        if entry.department not in dept_names:
            continue
        by_department.setdefault(entry.department, []).append(entry)

    departments_out: List[dict] = []
    overall_method: AnalysisMethod = "heuristic"

    target_depts = [department] if department else sorted(dept_names)
    for dept in target_depts:
        dept_logs = by_department.get(dept, [])
        groups, analysis_method = group_prompt_logs(dept_logs, method=method)
        if analysis_method == "mixed":
            overall_method = "mixed"
        elif analysis_method == "cluster" and overall_method == "heuristic":
            overall_method = "cluster"

        stat = next((item for item in known_departments if item.department == dept), None)
        total_requests = stat.total_requests if stat else len(dept_logs)
        departments_out.append(
            summarize_department_patterns(
                dept,
                groups,
                min_pattern_count=min_pattern_count,
                total_requests=total_requests,
            )
        )

    departments_out.sort(key=lambda item: item["repeat_ratio"], reverse=True)

    return {
        "period": {
            "from_date": date_range.from_date,
            "to_date": date_range.to_date,
        },
        "analysis_method": overall_method,
        "min_pattern_count": min_pattern_count,
        "departments": departments_out,
    }
