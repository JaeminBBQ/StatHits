"""Tests for the pure parsing layer against anonymized fixture data."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from didyouhit.parsing import parse_match_summary, parse_member_game

FIXTURES = Path(__file__).parent / "fixtures"
MIN_DURATION_S = 300


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


ARENA_MATCH = "match_1750_NA1_5638612201.json"
ARENA_TIMELINE = "timeline_1750_NA1_5638612201.json"
NORMAL_MATCH = "match_400_NA1_5438163867.json"
NORMAL_TIMELINE = "timeline_400_NA1_5438163867.json"
MATCH_1740 = "match_1740_NA1_5634363156.json"
TIMELINE_1740 = "timeline_1740_NA1_5634363156.json"


def test_arena_match_summary():
    summary = parse_match_summary(load(ARENA_MATCH), min_duration_s=MIN_DURATION_S)
    assert summary.match_id == "NA1_5638612201"
    assert summary.platform == "na1"
    assert summary.queue_id == 1750
    assert summary.game_mode == "CHERRY"
    assert summary.is_arena is True
    assert summary.is_valid is True
    assert summary.duration_s == 1454  # 24:14
    assert summary.game_end_ms == 1788938554862


def test_normal_match_is_not_arena():
    summary = parse_match_summary(load(NORMAL_MATCH), min_duration_s=MIN_DURATION_S)
    assert summary.is_arena is False
    assert summary.queue_id == 400
    assert summary.game_mode == "CLASSIC"


def test_member_game_full_stats():
    game = parse_member_game(load(ARENA_MATCH), load(ARENA_TIMELINE), "fixture-puuid-01")
    assert game is not None
    assert game.champion_name == "Heimerdinger"
    assert game.champion_id == 74
    assert game.placement == 2
    assert game.subteam_id == 1
    assert game.augments == [205, 65, 45, 93]
    assert game.damage_to_champions == 53976
    assert game.magic_damage_to_champions == 52425
    assert game.largest_crit == 0
    assert game.damage_mitigated == 28788
    assert game.cc_time == 56
    assert game.gold_earned == 18674
    assert game.damage_per_minute is not None and game.damage_per_minute > 2000
    assert game.final_ap == 1028
    assert game.peak_ap == 1028
    assert game.final_health_max == 4543
    assert game.final_attack_speed == 123
    assert game.peak_attack_speed == 154
    assert game.duration_s == 1454


def test_puuid_not_in_match_returns_none():
    game = parse_member_game(load(ARENA_MATCH), load(ARENA_TIMELINE), "fixture-puuid-99")
    assert game is None


def test_missing_timeline_sets_timeline_fields_none():
    game = parse_member_game(load(ARENA_MATCH), None, "fixture-puuid-01")
    assert game is not None
    assert game.damage_to_champions == 53976  # match fields still populated
    assert game.final_ap is None
    assert game.peak_ap is None
    assert game.final_health_max is None
    assert game.peak_attack_speed is None


def test_early_surrender_is_invalid():
    match = deepcopy(load(ARENA_MATCH))
    match["info"]["participants"][0]["gameEndedInEarlySurrender"] = True
    summary = parse_match_summary(match, min_duration_s=MIN_DURATION_S)
    assert summary.is_valid is False


def test_duration_threshold():
    short = deepcopy(load(ARENA_MATCH))
    short["info"]["gameDuration"] = 120
    assert parse_match_summary(short, min_duration_s=MIN_DURATION_S).is_valid is False

    boundary = deepcopy(load(ARENA_MATCH))
    boundary["info"]["gameDuration"] = MIN_DURATION_S
    assert parse_match_summary(boundary, min_duration_s=MIN_DURATION_S).is_valid is True

    high_threshold = parse_match_summary(load(ARENA_MATCH), min_duration_s=2000)
    assert high_threshold.is_valid is False


def test_duration_in_milliseconds_is_divided():
    match = deepcopy(load(ARENA_MATCH))
    match["info"]["gameDuration"] = 1454000
    summary = parse_match_summary(match, min_duration_s=MIN_DURATION_S)
    assert summary.duration_s == 1454


def test_all_1740_participants_parse():
    match = load(MATCH_1740)
    timeline = load(TIMELINE_1740)
    puuids = [p["puuid"] for p in match["info"]["participants"]]
    assert len(puuids) == 18
    for puuid in puuids:
        game = parse_member_game(match, timeline, puuid)
        assert game is not None, puuid
        assert 1 <= game.placement <= 6
        assert game.champion_name
        assert all(isinstance(augment, int) for augment in game.augments)


def test_normal_match_participants_parse():
    match = load(NORMAL_MATCH)
    timeline = load(NORMAL_TIMELINE)
    for participant in match["info"]["participants"]:
        game = parse_member_game(match, timeline, participant["puuid"])
        assert game is not None
        assert game.subteam_id == 0  # Riot sends 0, not a missing field, outside Arena
        assert game.damage_to_champions is not None
