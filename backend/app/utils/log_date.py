"""CSV prompt_logs.created_at 파싱 — 대시보드 기간 필터 공통."""

from __future__ import annotations

from datetime import date, datetime


def parse_log_date(created_at: str) -> date | None:
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


def log_month_key(created_at: str) -> str | None:
    """created_at → YYYY-MM (월별 업로드 분할·집계용)."""
    log_date = parse_log_date(created_at)
    if log_date is None:
        return None
    return log_date.strftime("%Y-%m")


def date_in_range(log_date: date, from_date: str, to_date: str) -> bool:
    start = date.fromisoformat(from_date)
    end = date.fromisoformat(to_date)
    return start <= log_date <= end
