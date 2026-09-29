"""Week window math: local-Monday weeks, labels, and the reset countdown.

A week runs Monday 00:00 -> next Monday 00:00 in the given time zone (D8).
Days are added in local time, so a week that contains a DST change is 167 or
169 hours long; callers must never add a fixed 7 days of milliseconds.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

MILLIS_PER_SECOND = 1000


def week_start_ms(ts_ms: int, tz: str) -> int:
    """UTC epoch ms of Monday 00:00 local time, for the week containing ts_ms."""
    local = datetime.fromtimestamp(ts_ms / MILLIS_PER_SECOND, tz=ZoneInfo(tz))
    monday = local - timedelta(days=local.weekday())
    midnight = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp() * MILLIS_PER_SECOND)


def week_bounds(ts_ms: int, tz: str) -> tuple[int, int]:
    """[start, end) of the week containing ts_ms; end is the next local Monday 00:00."""
    start_ms = week_start_ms(ts_ms, tz)
    start_local = datetime.fromtimestamp(start_ms / MILLIS_PER_SECOND, tz=ZoneInfo(tz))
    end_local = start_local + timedelta(days=7)
    return start_ms, int(end_local.timestamp() * MILLIS_PER_SECOND)


def week_label(start_ms: int, tz: str) -> str:
    """The local Monday date of a week start, e.g. "2026-09-28"."""
    local = datetime.fromtimestamp(start_ms / MILLIS_PER_SECOND, tz=ZoneInfo(tz))
    return local.strftime("%Y-%m-%d")


def week_from_label(label: str, tz: str) -> int:
    """Inverse of week_label: epoch ms of local midnight for the given date."""
    naive = datetime.strptime(label, "%Y-%m-%d")
    local = naive.replace(tzinfo=ZoneInfo(tz))
    return int(local.timestamp() * MILLIS_PER_SECOND)


def ms_until_reset(now_ms: int, tz: str) -> int:
    """Milliseconds until the current week ends (the next local Monday 00:00)."""
    _, end_ms = week_bounds(now_ms, tz)
    return end_ms - now_ms
