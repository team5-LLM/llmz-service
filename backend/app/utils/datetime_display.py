"""API 응답용 시각 표시 (KST)."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_KST = ZoneInfo("Asia/Seoul")


def format_datetime_kst(iso: str | None) -> str | None:
    """ISO-8601 UTC → 'YYYY-MM-DD HH:MM:SS' (Asia/Seoul). 파싱 실패 시 원문 반환."""
    if not iso:
        return iso
    try:
        normalized = iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_KST).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return iso
