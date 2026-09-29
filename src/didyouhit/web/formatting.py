"""Pure display formatting for values, dates and the reset countdown.

All epoch milliseconds stay integers through here; conversion to the display
time zone happens only in these functions. Per the formatting rules:
integers get thousands separators, per-minute dmg/HP are integers, s/min gets
one decimal, seconds boards show `56s`, totals are integers.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

HOUR_MS = 3_600_000
DAY_MS = 86_400_000


def intcomma(value: float | int | None) -> str:
    """Thousands separators on an integer, e.g. 53976 -> "53,976"."""
    if value is None:
        return "—"
    return f"{int(round(value)):,}"


def board_value(value: float | int | None, unit: str) -> str:
    """Format one board value according to its unit's rules."""
    if value is None:
        return "—"
    if unit == "s/min":
        return f"{value:.1f}"
    if unit == "s":
        return f"{int(round(value))}s"
    return intcomma(value)


def ordinal(number: int) -> str:
    """1 -> "1st", 2 -> "2nd", 3 -> "3rd", 11 -> "11th"."""
    if 10 <= number % 100 <= 20:
        return f"{number}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def format_dt(ts_ms: int | None, tz: str) -> str:
    """Date and time in the display zone, e.g. "Sep 8, 9:14 PM"."""
    if ts_ms is None:
        return "—"
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=ZoneInfo(tz))
    return f"{dt.strftime('%b')} {dt.day}, {dt.strftime('%I:%M %p').lstrip('0')}"


def format_date(ts_ms: int | None, tz: str) -> str:
    """Date in the display zone, e.g. "Sep 8, 2026"."""
    if ts_ms is None:
        return "—"
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=ZoneInfo(tz))
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}"


def reset_countdown(ms_until_reset: int) -> str:
    """Milliseconds until reset as "Xd Yh"."""
    days = ms_until_reset // DAY_MS
    hours = (ms_until_reset % DAY_MS) // HOUR_MS
    return f"{days}d {hours}h"
