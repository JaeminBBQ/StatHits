"""Tests for the boards: pure computation over GameRows and the DB layer."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from didyouhit.boards import (
    BOARDS,
    GameRow,
    MemberInfo,
    compute_boards,
    member_history,
    past_weeks,
    weekly_boards,
)
from didyouhit.models import Member, MemberGame
from didyouhit.parsing import parse_member_game
from didyouhit.weeks import week_start_ms

FIXTURES = Path(__file__).parent / "fixtures"
LA = "America/Los_Angeles"
HOUR_MS = 3_600_000


def local_ms(year: int, month: int, day: int, hour: int = 12) -> int:
    return int(datetime(year, month, day, hour, tzinfo=ZoneInfo(LA)).timestamp() * 1000)


def make_row(
    member_id: int,
    *,
    match_id: str = "M",
    game_end_ms: int = 1_000,
    placement: int | None = None,
    peak_ap: float | None = None,
    peak_ad: float | None = None,
    peak_health_max: float | None = None,
    largest_crit: int | None = None,
    damage_to_champions: int | None = None,
    damage_mitigated: int | None = None,
    heals_on_teammates: int | None = None,
    shields_on_teammates: int | None = None,
    cc_time: int | None = None,
    duration_s: int | None = None,
) -> GameRow:
    return GameRow(
        member_id=member_id,
        match_id=match_id,
        champion_name="Champ",
        game_end_ms=game_end_ms,
        duration_s=duration_s,
        placement=placement,
        peak_ap=peak_ap,
        peak_ad=peak_ad,
        peak_health_max=peak_health_max,
        largest_crit=largest_crit,
        damage_to_champions=damage_to_champions,
        damage_mitigated=damage_mitigated,
        heals_on_teammates=heals_on_teammates,
        shields_on_teammates=shields_on_teammates,
        cc_time=cc_time,
    )


def make_members(*ids: int, active: bool = True) -> dict[int, MemberInfo]:
    return {
        member_id: MemberInfo(member_id, f"Name{member_id}", "NA1", active) for member_id in ids
    }


def test_each_member_appears_once_with_best_game():
    games = [
        make_row(1, match_id="M1", game_end_ms=100, peak_ap=500),
        make_row(1, match_id="M2", game_end_ms=200, peak_ap=900),
        make_row(2, match_id="M3", game_end_ms=150, peak_ap=700),
    ]
    entries = compute_boards(games, make_members(1, 2))["peak_ap"]
    assert [(e.position, e.member_id, e.value, e.match_id) for e in entries] == [
        (1, 1, 900.0, "M2"),
        (2, 2, 700.0, "M3"),
    ]
    assert entries[0].riot_id == "Name1#NA1"
    assert entries[0].champion_name == "Champ"


def test_limit_respected():
    games = [make_row(i, match_id=f"M{i}", game_end_ms=i, peak_ap=i * 100) for i in range(1, 7)]
    entries = compute_boards(games, make_members(*range(1, 7)), limit=3)["peak_ap"]
    assert len(entries) == 3
    assert [e.member_id for e in entries] == [6, 5, 4]


def test_tie_on_value_goes_to_earlier_game():
    games = [
        make_row(1, match_id="late", game_end_ms=200, peak_ap=800),
        make_row(2, match_id="early", game_end_ms=100, peak_ap=800),
    ]
    entries = compute_boards(games, make_members(1, 2))["peak_ap"]
    assert [e.member_id for e in entries] == [2, 1]


def test_null_values_are_ignored():
    games = [
        make_row(1, match_id="M1", game_end_ms=100, peak_ap=None),
        make_row(2, match_id="M2", game_end_ms=200, peak_ap=123),
    ]
    entries = compute_boards(games, make_members(1, 2))["peak_ap"]
    assert [e.member_id for e in entries] == [2]


def test_ally_heal_shield_null_handling():
    games = [
        make_row(1, match_id="M1", game_end_ms=100, heals_on_teammates=100),
        make_row(
            2, match_id="M2", game_end_ms=200, heals_on_teammates=None, shields_on_teammates=None
        ),
        make_row(3, match_id="M3", game_end_ms=300, heals_on_teammates=50, shields_on_teammates=30),
    ]
    entries = compute_boards(games, make_members(1, 2, 3))["ally_heal_shield"]
    assert [(e.member_id, e.value) for e in entries] == [(1, 100.0), (3, 80.0)]


def test_per_minute_orders_differently_from_raw():
    games = [
        make_row(1, match_id="short", game_end_ms=100, damage_to_champions=20_000, duration_s=600),
        make_row(2, match_id="long", game_end_ms=200, damage_to_champions=45_000, duration_s=1800),
    ]
    members = make_members(1, 2)
    raw = compute_boards(games, members)["damage_to_champions"]
    assert [e.member_id for e in raw] == [2, 1]
    per_minute = compute_boards(games, members)["damage_to_champions_per_min"]
    assert [e.member_id for e in per_minute] == [1, 2]
    assert per_minute[0].value == pytest.approx(2000.0)
    assert per_minute[1].value == pytest.approx(1500.0)


def test_per_minute_skips_missing_duration():
    games = [
        make_row(1, match_id="M1", game_end_ms=100, damage_to_champions=30_000, duration_s=None),
        make_row(2, match_id="M2", game_end_ms=200, damage_to_champions=30_000, duration_s=0),
    ]
    assert compute_boards(games, make_members(1, 2))["damage_to_champions_per_min"] == []


def test_first_places_counts_and_tie_rule():
    games = [
        # member 1: two firsts, the second one at t=300
        make_row(1, match_id="a", game_end_ms=100, placement=1),
        make_row(1, match_id="b", game_end_ms=300, placement=1),
        make_row(1, match_id="c", game_end_ms=400, placement=2),
        # member 2: two firsts, the second one at t=250
        make_row(2, match_id="d", game_end_ms=200, placement=1),
        make_row(2, match_id="e", game_end_ms=250, placement=1),
        # member 3: one first
        make_row(3, match_id="f", game_end_ms=500, placement=1),
    ]
    entries = compute_boards(games, make_members(1, 2, 3, 4))["first_places"]
    assert [(e.member_id, e.value) for e in entries] == [(2, 2.0), (1, 2.0), (3, 1.0)]
    assert all(e.match_id is None and e.champion_name is None for e in entries)


def test_games_played_counts_all_games():
    games = [
        make_row(1, match_id="a", game_end_ms=100),
        make_row(1, match_id="b", game_end_ms=200),
        make_row(2, match_id="c", game_end_ms=300),
    ]
    entries = compute_boards(games, make_members(1, 2))["games_played"]
    assert [(e.member_id, e.value) for e in entries] == [(1, 2.0), (2, 1.0)]


def test_inactive_members_are_excluded():
    games = [make_row(1, match_id="M1", game_end_ms=100, peak_ap=500)]
    members = {1: MemberInfo(1, "Name1", "NA1", active=False)}
    assert compute_boards(games, members)["peak_ap"] == []
    assert compute_boards(games, members)["games_played"] == []


def test_every_board_key_present_even_with_no_games():
    boards = compute_boards([], {})
    assert set(boards) == {board.key for board in BOARDS}
    assert all(entries == [] for entries in boards.values())


def test_no_banned_wording_in_boards():
    for board in BOARDS:
        for text in (board.key, board.label):
            assert not re.search(r"\b(rank|tier|mmr|elo)\b", text, re.IGNORECASE), text


def add_member_row(session, puuid: str = "fixture-puuid-01") -> Member:
    member = Member(
        puuid=puuid,
        game_name="GameName",
        tag_line="NA1",
        platform="na1",
        created_at_ms=1,
        active=True,
        last_polled_at_ms=None,
        backfill_from_ms=1,
    )
    session.add(member)
    session.commit()
    return member


def insert_game(session, member_id: int, *, match_id: str, game_end_ms: int, **fields) -> None:
    session.add(
        MemberGame(
            member_id=member_id,
            match_id=match_id,
            champion_name="Heimerdinger",
            game_end_ms=game_end_ms,
            **fields,
        )
    )
    session.commit()


def test_weekly_boards_only_sees_the_requested_week(session):
    member = add_member_row(session)
    week1_start = week_start_ms(local_ms(2026, 9, 28), LA)
    week2_start = week_start_ms(local_ms(2026, 10, 5), LA)
    insert_game(session, member.id, match_id="M1", game_end_ms=week1_start + HOUR_MS, peak_ap=500)
    insert_game(session, member.id, match_id="M2", game_end_ms=week2_start + HOUR_MS, peak_ap=900)

    boards = weekly_boards(session, week1_start + HOUR_MS, LA)
    entries = boards["peak_ap"]
    assert [(e.match_id, e.value) for e in entries] == [("M1", 500.0)]


def test_past_weeks_excludes_current_week_and_orders_newest_first(session):
    member = add_member_row(session)
    current_start = week_start_ms(local_ms(2026, 10, 12), LA)
    week1_start = week_start_ms(local_ms(2026, 9, 28), LA)
    week2_start = week_start_ms(local_ms(2026, 10, 5), LA)
    insert_game(session, member.id, match_id="M1", game_end_ms=week1_start + HOUR_MS, peak_ap=500)
    insert_game(session, member.id, match_id="M2", game_end_ms=week2_start + HOUR_MS, peak_ap=900)
    insert_game(session, member.id, match_id="M3", game_end_ms=current_start + HOUR_MS, peak_ap=999)

    weeks = past_weeks(session, current_start + HOUR_MS, LA)
    assert [week.label for week in weeks] == ["2026-10-05", "2026-09-28"]
    assert weeks[0].winners["peak_ap"] is not None
    assert weeks[0].winners["peak_ap"].match_id == "M2"
    assert weeks[1].winners["peak_ap"].match_id == "M1"
    assert weeks[0].winners["first_places"] is None  # no firsts in that week


def test_member_history_newest_first_with_limit(session):
    member = add_member_row(session)
    for i, game_end_ms in enumerate([1000, 3000, 2000, 5000]):
        insert_game(session, member.id, match_id=f"M{i}", game_end_ms=game_end_ms)

    history = member_history(session, member.id, limit=2)
    assert [row.game_end_ms for row in history] == [5000, 3000]
    assert len(member_history(session, member.id)) == 4
    assert [row.game_end_ms for row in member_history(session, member.id, before_ms=3000)] == [
        2000,
        1000,
    ]


def test_fixture_game_shows_on_boards(session):
    member = add_member_row(session)
    match = json.loads((FIXTURES / "match_1750_NA1_5638612201.json").read_text())
    timeline = json.loads((FIXTURES / "timeline_1750_NA1_5638612201.json").read_text())
    game = parse_member_game(match, timeline, "fixture-puuid-01")
    assert game is not None
    fields = asdict(game)
    fields.pop("match_id")
    session.add(MemberGame(member_id=member.id, match_id="NA1_5638612201", **fields))
    session.commit()

    boards = weekly_boards(session, game.game_end_ms, LA)
    damage = boards["damage_to_champions"]
    peak_ap = boards["peak_ap"]
    assert len(damage) == 1
    assert damage[0].value == 53976
    assert damage[0].match_id == "NA1_5638612201"
    assert damage[0].champion_name == "Heimerdinger"
    assert peak_ap[0].value == 1028
