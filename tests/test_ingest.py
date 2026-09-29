"""Tests for the ingestion service against the anonymized fixtures (mocked HTTP)."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import JSON, MetaData, String, Table, Text, func, inspect, select

from didyouhit.ingest import IngestStats, add_member, ingest_all
from didyouhit.models import Match, Member, MemberGame
from didyouhit.riot.client import RiotClient
from didyouhit.riot.errors import RiotAuthError

FIXTURES = Path(__file__).parent / "fixtures"
MIN_DURATION_S = 300

ARENA_MATCH_ID = "NA1_5638612201"
NORMAL_MATCH_ID = "NA1_5438163867"
ARENA_MATCH_URL = f"https://americas.api.riotgames.com/lol/match/v5/matches/{ARENA_MATCH_ID}"
ARENA_TIMELINE_URL = f"{ARENA_MATCH_URL}/timeline"
NORMAL_MATCH_URL = f"https://americas.api.riotgames.com/lol/match/v5/matches/{NORMAL_MATCH_ID}"
ACCOUNT_PREFIX = "https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def ids_url(puuid: str) -> str:
    return f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"


def make_member(
    puuid: str,
    *,
    backfill_from_ms: int | None = 1_000_000_000_000,
    last_polled_at_ms: int | None = None,
) -> Member:
    return Member(
        puuid=puuid,
        game_name="Fixture",
        tag_line="NA1",
        platform="na1",
        created_at_ms=1_000_000_000_000,
        active=True,
        last_polled_at_ms=last_polled_at_ms,
        backfill_from_ms=backfill_from_ms,
    )


def mock_listing(router: respx.MockRouter, puuid: str, match_ids: list[str]) -> respx.Route:
    return router.get(url__startswith=ids_url(puuid)).mock(
        return_value=httpx.Response(200, json=match_ids)
    )


def mock_arena_match(router: respx.MockRouter) -> tuple[respx.Route, respx.Route]:
    """Mock the 1750 fixture's match and timeline; returns the two routes."""
    match_route = router.get(ARENA_MATCH_URL).mock(
        return_value=httpx.Response(200, json=load("match_1750_NA1_5638612201.json"))
    )
    timeline_route = router.get(ARENA_TIMELINE_URL).mock(
        return_value=httpx.Response(200, json=load("timeline_1750_NA1_5638612201.json"))
    )
    return match_route, timeline_route


def test_two_members_in_one_match_share_one_fetch(session, api_key, clock, sleeper):
    session.add_all([make_member("fixture-puuid-01"), make_member("fixture-puuid-02")])
    session.commit()
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        listing01 = mock_listing(router, "fixture-puuid-01", [ARENA_MATCH_ID])
        listing02 = mock_listing(router, "fixture-puuid-02", [ARENA_MATCH_ID])
        match_route, timeline_route = mock_arena_match(router)
        client = RiotClient(api_key, clock=clock, sleep=sleeper)
        stats = ingest_all(session, client, now_ms=2_000_000_000_000, min_duration_s=MIN_DURATION_S)
        assert listing01.call_count == 1 and listing02.call_count == 1
        assert match_route.call_count == 1
        assert timeline_route.call_count == 1

    assert stats.members == 2
    assert stats.ids_listed == 2
    assert stats.matches_fetched == 1
    assert stats.timelines_fetched == 1
    assert stats.member_games_created == 2
    assert stats.errors == 0

    games = session.scalars(select(MemberGame).order_by(MemberGame.member_id)).all()
    assert len(games) == 2
    member01_game = games[0]
    assert member01_game.match_id == ARENA_MATCH_ID
    assert member01_game.champion_name == "Heimerdinger"
    assert member01_game.champion_id == 74
    assert member01_game.placement == 2
    assert member01_game.subteam_id == 1
    assert member01_game.augments == [205, 65, 45, 93]
    assert member01_game.damage_to_champions == 53976
    assert member01_game.magic_damage_to_champions == 52425
    assert member01_game.gold_earned == 18674
    assert member01_game.final_ap == 1028
    assert member01_game.peak_attack_speed == 154
    assert member01_game.duration_s == 1454


def test_normal_game_recorded_without_timeline(session, api_key, clock, sleeper):
    session.add(make_member("fixture-puuid-01"))
    session.commit()
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        mock_listing(router, "fixture-puuid-01", [NORMAL_MATCH_ID])
        router.get(NORMAL_MATCH_URL).mock(
            return_value=httpx.Response(200, json=load("match_400_NA1_5438163867.json"))
        )
        timeline_route = router.get(f"{NORMAL_MATCH_URL}/timeline").mock(
            return_value=httpx.Response(200, json={})
        )
        ingest_all(
            session,
            RiotClient(api_key, clock=clock, sleep=sleeper),
            now_ms=2_000_000_000_000,
            min_duration_s=MIN_DURATION_S,
        )
        assert timeline_route.call_count == 0

    row = session.get(Match, NORMAL_MATCH_ID)
    assert row is not None
    assert row.is_arena is False
    assert session.scalars(select(MemberGame)).all() == []


def test_second_run_with_same_listing_does_no_fetches(session, api_key, clock, sleeper):
    session.add_all([make_member("fixture-puuid-01"), make_member("fixture-puuid-02")])
    session.commit()
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        mock_listing(router, "fixture-puuid-01", [ARENA_MATCH_ID])
        mock_listing(router, "fixture-puuid-02", [ARENA_MATCH_ID])
        match_route, timeline_route = mock_arena_match(router)
        client = RiotClient(api_key, clock=clock, sleep=sleeper)
        ingest_all(session, client, now_ms=2_000_000_000_000, min_duration_s=MIN_DURATION_S)
        calls_after_first = client.calls

        stats = ingest_all(session, client, now_ms=2_100_000_000_000, min_duration_s=MIN_DURATION_S)
        assert client.calls - calls_after_first == 2  # just the two listing calls
        assert match_route.call_count == 1
        assert timeline_route.call_count == 1

    assert stats.matches_fetched == 0
    assert stats.timelines_fetched == 0
    assert stats.member_games_created == 0
    assert stats.ids_listed == 2


def test_remake_recorded_invalid_without_member_games(session, api_key, clock, sleeper):
    session.add(make_member("fixture-puuid-01"))
    session.commit()
    remake = deepcopy(load("match_1750_NA1_5638612201.json"))
    remake["info"]["participants"][0]["gameEndedInEarlySurrender"] = True
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        mock_listing(router, "fixture-puuid-01", [ARENA_MATCH_ID])
        router.get(ARENA_MATCH_URL).mock(return_value=httpx.Response(200, json=remake))
        timeline_route = router.get(ARENA_TIMELINE_URL).mock(
            return_value=httpx.Response(200, json=load("timeline_1750_NA1_5638612201.json"))
        )
        ingest_all(
            session,
            RiotClient(api_key, clock=clock, sleep=sleeper),
            now_ms=2_000_000_000_000,
            min_duration_s=MIN_DURATION_S,
        )
        assert timeline_route.call_count == 0

    row = session.get(Match, ARENA_MATCH_ID)
    assert row is not None
    assert row.is_arena is True
    assert row.is_valid is False
    assert session.scalars(select(MemberGame)).all() == []


def test_later_member_backfills_existing_match(session, api_key, clock, sleeper):
    member01 = make_member("fixture-puuid-01")
    session.add(member01)
    session.commit()
    account = {"puuid": "fixture-puuid-03", "gameName": "LateName", "tagLine": "NA1"}
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(url__startswith=ACCOUNT_PREFIX).mock(
            return_value=httpx.Response(200, json=account)
        )
        mock_listing(router, "fixture-puuid-01", [ARENA_MATCH_ID])
        match_route, timeline_route = mock_arena_match(router)
        client = RiotClient(api_key, clock=clock, sleep=sleeper)
        ingest_all(session, client, now_ms=2_000_000_000_000, min_duration_s=MIN_DURATION_S)
        assert match_route.call_count == 1
        assert timeline_route.call_count == 1

        member03 = add_member(
            session, client, "LateName#NA1", "na1", now_ms=2_000_000_000_000, backfill_days=7
        )
        session.commit()
        listing03 = mock_listing(router, "fixture-puuid-03", [ARENA_MATCH_ID])
        stats = ingest_all(session, client, now_ms=2_100_000_000_000, min_duration_s=MIN_DURATION_S)
        assert listing03.call_count == 1
        assert match_route.call_count == 2
        assert timeline_route.call_count == 2

    assert stats.matches_fetched == 1
    assert stats.timelines_fetched == 1
    assert stats.member_games_created == 1
    games = session.scalars(select(MemberGame).order_by(MemberGame.member_id)).all()
    assert [game.member_id for game in games] == [member01.id, member03.id]


def test_match_404_recorded_as_seen_and_not_retried(session, api_key, clock, sleeper):
    member = make_member("fixture-puuid-01")
    session.add(member)
    session.commit()
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        mock_listing(router, "fixture-puuid-01", ["NA1_9999999999"])
        missing_route = router.get(
            "https://americas.api.riotgames.com/lol/match/v5/matches/NA1_9999999999"
        ).mock(return_value=httpx.Response(404))
        client = RiotClient(api_key, clock=clock, sleep=sleeper)

        stats1 = ingest_all(
            session, client, now_ms=2_000_000_000_000, min_duration_s=MIN_DURATION_S
        )
        assert stats1.errors == 1
        assert stats1.retryable_failures == 0  # recorded failures don't hold the cursor
        row = session.get(Match, "NA1_9999999999")
        assert row is not None
        assert row.is_arena is False
        assert row.is_valid is False

        stats2 = ingest_all(
            session, client, now_ms=2_100_000_000_000, min_duration_s=MIN_DURATION_S
        )
        assert missing_route.call_count == 1  # never fetched again

    assert stats2.errors == 0
    assert (
        member.last_polled_at_ms == 2_100_000_000_000
    )  # cursor advanced past the 404 (run 2 to the new now)


def test_timeline_503s_skip_match_and_retry_next_poll(session, api_key, clock, sleeper):
    member = make_member("fixture-puuid-01")
    session.add(member)
    session.commit()
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        mock_listing(router, "fixture-puuid-01", [ARENA_MATCH_ID])
        match_route = router.get(ARENA_MATCH_URL).mock(
            return_value=httpx.Response(200, json=load("match_1750_NA1_5638612201.json"))
        )
        timeline_route = router.get(ARENA_TIMELINE_URL).mock(return_value=httpx.Response(503))
        client = RiotClient(api_key, clock=clock, sleep=sleeper)

        stats1 = ingest_all(
            session, client, now_ms=2_000_000_000_000, min_duration_s=MIN_DURATION_S
        )
        assert stats1.errors == 1
        assert stats1.retryable_failures == 1
        assert session.get(Match, ARENA_MATCH_ID) is None
        assert member.last_polled_at_ms is None  # cursor held
        assert timeline_route.call_count == 5

        stats2 = ingest_all(
            session, client, now_ms=2_100_000_000_000, min_duration_s=MIN_DURATION_S
        )
        assert stats2.errors == 1
        assert stats2.retryable_failures == 1
        assert session.get(Match, ARENA_MATCH_ID) is None
        assert match_route.call_count == 2  # the match is fetched again on the next run
        assert timeline_route.call_count == 10


def test_401_on_listing_raises_from_ingest_all(session, api_key, clock, sleeper):
    session.add(make_member("fixture-puuid-01"))
    session.commit()
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(url__startswith=ids_url("fixture-puuid-01")).mock(
            return_value=httpx.Response(401)
        )
        with pytest.raises(RiotAuthError):
            ingest_all(
                session,
                RiotClient(api_key, clock=clock, sleep=sleeper),
                now_ms=2_000_000_000_000,
                min_duration_s=MIN_DURATION_S,
            )


def test_add_member_stores_canonical_riot_id_and_dedupes(session, api_key, clock, sleeper):
    account = {"puuid": "fixture-puuid-01", "gameName": "Lowercase", "tagLine": "NA1"}
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(url__startswith=ACCOUNT_PREFIX).mock(
            return_value=httpx.Response(200, json=account)
        )
        client = RiotClient(api_key, clock=clock, sleep=sleeper)
        now_ms = 2_000_000_000_000
        member1 = add_member(
            session, client, "lowercase#NA1", "na1", now_ms=now_ms, backfill_days=7
        )
        session.commit()
        member2 = add_member(
            session, client, "whatever#NA1", "na1", now_ms=now_ms + 1, backfill_days=7
        )
        session.commit()

    assert member1.game_name == "Lowercase"
    assert member1.tag_line == "NA1"
    assert member1.active is True
    assert member1.last_polled_at_ms is None
    assert member1.backfill_from_ms == now_ms - 7 * 86_400_000
    assert member2.id == member1.id
    assert session.scalar(select(func.count()).select_from(Member)) == 1


def test_add_member_rejects_bad_riot_id(session, api_key, clock, sleeper):
    client = RiotClient(api_key, clock=clock, sleep=sleeper)
    with pytest.raises(ValueError):
        add_member(session, client, "NoTag", "na1", now_ms=1, backfill_days=7)
    with pytest.raises(ValueError):
        add_member(session, client, "#NA1", "na1", now_ms=1, backfill_days=7)


def test_start_time_uses_one_hour_overlap(session, api_key, clock, sleeper):
    member = make_member(
        "fixture-puuid-01",
        backfill_from_ms=1_000_000_000_000,
        last_polled_at_ms=2_000_000_000_000,
    )
    session.add(member)
    session.commit()
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        listing = mock_listing(router, "fixture-puuid-01", [])
        ingest_all(
            session,
            RiotClient(api_key, clock=clock, sleep=sleeper),
            now_ms=2_100_000_000_000,
            min_duration_s=MIN_DURATION_S,
        )
        assert listing.calls[0].request.url.params["startTime"] == "1999996400"

    assert member.last_polled_at_ms == 2_100_000_000_000


def test_start_time_defaults_backfill_to_seven_days(session, api_key, clock, sleeper):
    member = make_member("fixture-puuid-01", backfill_from_ms=None, last_polled_at_ms=None)
    session.add(member)
    session.commit()
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        listing = mock_listing(router, "fixture-puuid-01", [])
        ingest_all(
            session,
            RiotClient(api_key, clock=clock, sleep=sleeper),
            now_ms=10_000_000_000,
            min_duration_s=MIN_DURATION_S,
        )
        assert listing.calls[0].request.url.params["startTime"] == "9395200"


def test_no_non_member_data_persisted(session, api_key, clock, sleeper):
    session.add(make_member("fixture-puuid-01"))
    session.commit()
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        mock_listing(router, "fixture-puuid-01", [ARENA_MATCH_ID])
        mock_arena_match(router)
        ingest_all(
            session,
            RiotClient(api_key, clock=clock, sleep=sleeper),
            now_ms=2_000_000_000_000,
            min_duration_s=MIN_DURATION_S,
        )

    found_puuids: set[str] = set()
    inspector = inspect(session.get_bind())
    for table_name in inspector.get_table_names():
        table = Table(table_name, MetaData(), autoload_with=session.get_bind())
        for column in table.columns:
            if not isinstance(column.type, (String, Text, JSON)):
                continue
            for (value,) in session.execute(select(column)):
                if value is None:
                    continue
                text = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                found_puuids.update(re.findall(r"fixture-puuid-\d+", text))
                assert "Player0" not in text
                assert "Player1" not in text
    assert found_puuids <= {"fixture-puuid-01"}


def test_ingest_stats_sum():
    total = (
        IngestStats(members=1, ids_listed=2, matches_fetched=3, errors=4)
        + IngestStats(
            members=5, ids_listed=6, timelines_fetched=7, member_games_created=8, errors=1
        )
        + IngestStats(retryable_failures=2)
    )
    assert total == IngestStats(
        members=6,
        ids_listed=8,
        matches_fetched=3,
        timelines_fetched=7,
        member_games_created=8,
        errors=5,
        retryable_failures=2,
    )


def test_cursor_holds_on_retryable_failure_then_advances(session, api_key, clock, sleeper):
    member = make_member("fixture-puuid-01", last_polled_at_ms=2_000_000_000_000)
    session.add(member)
    session.commit()
    missing_url = "https://americas.api.riotgames.com/lol/match/v5/matches/NA1_9999999999"
    # Run 1: the arena match ingests, the other match 503s five times.
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        mock_listing(router, "fixture-puuid-01", [ARENA_MATCH_ID, "NA1_9999999999"])
        mock_arena_match(router)
        failing_route = router.get(missing_url).mock(return_value=httpx.Response(503))
        stats1 = ingest_all(
            session,
            RiotClient(api_key, clock=clock, sleep=sleeper),
            now_ms=2_100_000_000_000,
            min_duration_s=MIN_DURATION_S,
        )
        assert failing_route.call_count == 5

    assert stats1.errors == 1
    assert stats1.retryable_failures == 1
    assert member.last_polled_at_ms == 2_000_000_000_000  # cursor held
    assert session.get(Match, ARENA_MATCH_ID) is not None  # the good match still ingested
    assert session.get(Match, "NA1_9999999999") is None

    # Run 2: the failed match now works (serve the 1740 fixture under that id).
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        mock_listing(router, "fixture-puuid-01", [ARENA_MATCH_ID, "NA1_9999999999"])
        match_route = router.get(missing_url).mock(
            return_value=httpx.Response(200, json=load("match_1740_NA1_5634363156.json"))
        )
        timeline_route = router.get(f"{missing_url}/timeline").mock(
            return_value=httpx.Response(200, json=load("timeline_1740_NA1_5634363156.json"))
        )
        stats2 = ingest_all(
            session,
            RiotClient(api_key, clock=clock, sleep=sleeper),
            now_ms=2_200_000_000_000,
            min_duration_s=MIN_DURATION_S,
        )
        assert match_route.call_count == 1
        assert timeline_route.call_count == 1

    assert stats2.errors == 0
    assert stats2.retryable_failures == 0
    assert member.last_polled_at_ms == 2_200_000_000_000  # cursor advanced
    row = session.get(Match, "NA1_9999999999")
    assert row is not None and row.is_valid is True
    assert (
        session.scalar(
            select(MemberGame).where(
                MemberGame.member_id == member.id, MemberGame.match_id == "NA1_9999999999"
            )
        )
        is not None
    )


def test_match_403_with_valid_key_records_seen_and_continues(session, api_key, clock, sleeper):
    member = make_member("fixture-puuid-01")
    session.add(member)
    session.commit()
    forbidden_url = "https://americas.api.riotgames.com/lol/match/v5/matches/NA1_7777777777"
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        listing = mock_listing(router, "fixture-puuid-01", ["NA1_7777777777", NORMAL_MATCH_ID])
        forbidden_route = router.get(forbidden_url).mock(return_value=httpx.Response(403))
        router.get(NORMAL_MATCH_URL).mock(
            return_value=httpx.Response(200, json=load("match_400_NA1_5438163867.json"))
        )
        client = RiotClient(api_key, clock=clock, sleep=sleeper)
        stats1 = ingest_all(
            session, client, now_ms=2_000_000_000_000, min_duration_s=MIN_DURATION_S
        )
        assert forbidden_route.call_count == 1
        assert listing.call_count == 2  # the listing plus the key re-check

        stats2 = ingest_all(
            session, client, now_ms=2_100_000_000_000, min_duration_s=MIN_DURATION_S
        )
        assert forbidden_route.call_count == 1  # not requested again
        assert listing.call_count == 3  # one more listing, no more re-checks

    assert stats1.errors == 1
    assert stats1.retryable_failures == 0
    assert stats2.errors == 0
    row = session.get(Match, "NA1_7777777777")
    assert row is not None
    assert row.is_arena is False
    assert row.is_valid is False
    assert session.get(Match, NORMAL_MATCH_ID) is not None  # the other match still ingested
    assert member.last_polled_at_ms == 2_100_000_000_000  # cursor advanced (run 2 to the new now)


def test_match_403_with_dead_key_aborts(session, api_key, clock, sleeper):
    session.add(make_member("fixture-puuid-01"))
    session.commit()
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(url__startswith=ids_url("fixture-puuid-01")).mock(
            side_effect=[
                httpx.Response(200, json=["NA1_7777777777"]),
                httpx.Response(403),  # the key re-check
            ]
        )
        router.get("https://americas.api.riotgames.com/lol/match/v5/matches/NA1_7777777777").mock(
            return_value=httpx.Response(403)
        )
        with pytest.raises(RiotAuthError):
            ingest_all(
                session,
                RiotClient(api_key, clock=clock, sleep=sleeper),
                now_ms=2_000_000_000_000,
                min_duration_s=MIN_DURATION_S,
            )


def test_401_on_match_raises_without_recheck(session, api_key, clock, sleeper):
    session.add(make_member("fixture-puuid-01"))
    session.commit()
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        listing = mock_listing(router, "fixture-puuid-01", ["NA1_7777777777"])
        router.get("https://americas.api.riotgames.com/lol/match/v5/matches/NA1_7777777777").mock(
            return_value=httpx.Response(401)
        )
        with pytest.raises(RiotAuthError):
            ingest_all(
                session,
                RiotClient(api_key, clock=clock, sleep=sleeper),
                now_ms=2_000_000_000_000,
                min_duration_s=MIN_DURATION_S,
            )
        assert listing.call_count == 1  # no key re-check for a 401


def test_unexpected_400_on_match_is_retryable(session, api_key, clock, sleeper):
    member = make_member("fixture-puuid-01", last_polled_at_ms=2_000_000_000_000)
    session.add(member)
    session.commit()
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        mock_listing(router, "fixture-puuid-01", [ARENA_MATCH_ID, "NA1_8888888888"])
        mock_arena_match(router)
        router.get("https://americas.api.riotgames.com/lol/match/v5/matches/NA1_8888888888").mock(
            return_value=httpx.Response(400)
        )
        stats = ingest_all(
            session,
            RiotClient(api_key, clock=clock, sleep=sleeper),
            now_ms=2_100_000_000_000,
            min_duration_s=MIN_DURATION_S,
        )
    assert stats.errors == 1
    assert stats.retryable_failures == 1
    assert member.last_polled_at_ms == 2_000_000_000_000  # cursor held
    assert session.get(Match, "NA1_8888888888") is None  # not recorded
    assert session.get(Match, ARENA_MATCH_ID) is not None  # the other match still ingested


def test_unexpected_400_on_listing_skips_member(session, api_key, clock, sleeper):
    member01 = make_member("fixture-puuid-01")
    member02 = make_member("fixture-puuid-02")
    session.add_all([member01, member02])
    session.commit()
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(url__startswith=ids_url("fixture-puuid-01")).mock(
            return_value=httpx.Response(400)
        )
        mock_listing(router, "fixture-puuid-02", [ARENA_MATCH_ID])
        mock_arena_match(router)
        stats = ingest_all(
            session,
            RiotClient(api_key, clock=clock, sleep=sleeper),
            now_ms=2_000_000_000_000,
            min_duration_s=MIN_DURATION_S,
        )
    assert stats.errors == 1
    assert stats.members == 1  # only member 02 was processed
    assert member01.last_polled_at_ms is None  # cursor unchanged
    assert member02.last_polled_at_ms == 2_000_000_000_000
    assert session.scalars(select(MemberGame)).all() != []  # member 02 was ingested
