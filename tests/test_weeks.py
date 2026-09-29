"""Tests for the week window math (local-Monday weeks, DST-aware)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from didyouhit.weeks import ms_until_reset, week_bounds, week_from_label, week_label, week_start_ms

LA = "America/Los_Angeles"
HOUR_MS = 3_600_000


def local_ms(year: int, month: int, day: int, hour: int = 0, minute: int = 0, tz: str = LA) -> int:
    dt = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(tz))
    return int(dt.timestamp() * 1000)


def test_sunday_and_monday_midnight_are_different_weeks():
    sunday = local_ms(2026, 10, 4, 23, 59)
    monday = local_ms(2026, 10, 5, 0, 0)
    assert week_label(week_start_ms(sunday, LA), LA) == "2026-09-28"
    assert week_label(week_start_ms(monday, LA), LA) == "2026-10-05"
    assert week_start_ms(sunday, LA) != week_start_ms(monday, LA)
    assert week_bounds(sunday, LA) == (week_start_ms(sunday, LA), week_start_ms(monday, LA))


def test_week_label_round_trips():
    for ts_ms in (
        local_ms(2026, 9, 30, 12, 0),
        local_ms(2026, 1, 1, 0, 0),
        local_ms(2026, 11, 5, 0, 0),
    ):
        start = week_start_ms(ts_ms, LA)
        assert week_from_label(week_label(start, LA), LA) == start


def test_fall_back_week_is_169_hours():
    start = week_start_ms(local_ms(2026, 10, 27, 12, 0), LA)
    assert week_label(start, LA) == "2026-10-26"
    assert week_bounds(start, LA)[1] - week_bounds(start, LA)[0] == 169 * HOUR_MS


def test_spring_forward_weeks():
    # DST starts Sun 2026-03-08, before this Monday: 168h.
    start = week_start_ms(local_ms(2026, 3, 9, 12, 0), LA)
    assert week_label(start, LA) == "2026-03-09"
    assert week_bounds(start, LA)[1] - week_bounds(start, LA)[0] == 168 * HOUR_MS
    # The week of Mon 2026-03-02 contains the spring forward: 167h.
    start = week_start_ms(local_ms(2026, 3, 4, 12, 0), LA)
    assert week_label(start, LA) == "2026-03-02"
    assert week_bounds(start, LA)[1] - week_bounds(start, LA)[0] == 167 * HOUR_MS


def test_utc_week_is_168_hours():
    start = week_start_ms(local_ms(2026, 10, 27, 12, 0, tz="UTC"), "UTC")
    assert week_label(start, "UTC") == "2026-10-26"
    assert week_bounds(start, "UTC")[1] - week_bounds(start, "UTC")[0] == 168 * HOUR_MS


def test_ms_until_reset():
    monday = local_ms(2026, 9, 28, 0, 0)
    assert ms_until_reset(monday, LA) == 7 * 24 * HOUR_MS
    wednesday_noon = local_ms(2026, 9, 30, 12, 0)
    assert ms_until_reset(wednesday_noon, LA) == 5 * 24 * HOUR_MS - 12 * HOUR_MS
