"""공통 기간 필터 — from_date / to_date / month 파싱"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional


# 기간 범위 파싱 오류 (from_date > to_date)
class InvalidDateRangeError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


# 파싱 결과 (YYYY-MM-DD)
@dataclass(frozen=True)
class DateRange:
    from_date: str  # YYYY-MM-DD
    to_date: str  # YYYY-MM-DD

    @property
    def from_date_exclusive_upper(self) -> str:
        """to_date 다음 날 — uploaded_at < 이 값 으로 종료일 포함."""
        end = date.fromisoformat(self.to_date)
        return (end + timedelta(days=1)).isoformat()


_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")


# 기간 필터 해석 (dashboard / risk / uploads/history 공통)
def resolve_date_range(
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    month: Optional[str] = None,
) -> DateRange:
    """
    - month 지정 시 해당 월 1일~말일 (from_date/to_date 무시)
    - 파라미터 없음 → UTC 기준 직전 30일
    - from_date / to_date 개별 기본값: 30일 전 / 오늘
    - from_date > to_date → InvalidDateRangeError
    """
    if month:
        match = _MONTH_RE.match(month.strip())
        if not match:
            raise ValueError(f"month 형식은 YYYY-MM 이어야 합니다: {month!r}")
        year, mon = int(match.group(1)), int(match.group(2))
        if mon < 1 or mon > 12:
            raise ValueError(f"month 값이 유효하지 않습니다: {month!r}")
        last_day = calendar.monthrange(year, mon)[1]
        return DateRange(
            from_date=date(year, mon, 1).isoformat(),
            to_date=date(year, mon, last_day).isoformat(),
        )

    today = datetime.now(timezone.utc).date()

    if from_date is None and to_date is None:
        return DateRange(
            from_date=(today - timedelta(days=30)).isoformat(),
            to_date=today.isoformat(),
        )

    try:
        to_d = date.fromisoformat(to_date) if to_date else today
        from_d = (
            date.fromisoformat(from_date)
            if from_date
            else to_d - timedelta(days=30)
        )
    except ValueError as exc:
        raise ValueError(f"날짜 형식은 YYYY-MM-DD 이어야 합니다: {exc}") from exc

    if from_d > to_d:
        raise InvalidDateRangeError("from_date는 to_date보다 이후일 수 없습니다.")

    return DateRange(from_date=from_d.isoformat(), to_date=to_d.isoformat())
