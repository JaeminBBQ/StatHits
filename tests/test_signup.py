"""Tests for the sign-up boundary: invite-code checks and error mapping."""

from __future__ import annotations

import httpx
import pytest
import respx
from sqlalchemy import func, select

from didyouhit.models import Member
from didyouhit.riot.client import RiotClient
from didyouhit.signup import (
    InvalidRiotId,
    RiotIdNotFound,
    SignupUnavailable,
    check_invite_code,
    register_member,
)

ACCOUNT_PREFIX = "https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
NOW_MS = 2_000_000_000_000


def test_check_invite_code_matches_exactly():
    assert check_invite_code("sesame", "sesame") is True
    assert check_invite_code("SESAME", "sesame") is False
    assert check_invite_code("other", "sesame") is False


def test_check_invite_code_closed_without_expected():
    assert check_invite_code("anything", None) is False
    assert check_invite_code("anything", "") is False


def test_check_invite_code_rejects_missing_given():
    assert check_invite_code(None, "sesame") is False
    assert check_invite_code("", "sesame") is False


def test_register_member_creates_member(session, api_key, clock, sleeper):
    account = {"puuid": "fixture-puuid-01", "gameName": "Registered", "tagLine": "NA1"}
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(url__startswith=ACCOUNT_PREFIX).mock(
            return_value=httpx.Response(200, json=account)
        )
        member = register_member(
            session,
            RiotClient(api_key, clock=clock, sleep=sleeper),
            "Registered#NA1",
            "na1",
            now_ms=NOW_MS,
            backfill_days=7,
        )
    session.commit()
    assert member.game_name == "Registered"
    assert member.tag_line == "NA1"
    assert member.active is True
    assert member.backfill_from_ms == NOW_MS - 7 * 86_400_000
    assert session.scalar(select(func.count()).select_from(Member)) == 1


def test_register_member_maps_bad_format(session, api_key, clock, sleeper):
    with respx.mock(assert_all_mocked=True):
        with pytest.raises(InvalidRiotId):
            register_member(
                session,
                RiotClient(api_key, clock=clock, sleep=sleeper),
                "NoTag",
                "na1",
                now_ms=NOW_MS,
                backfill_days=7,
            )


def test_register_member_maps_not_found(session, api_key, clock, sleeper):
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(url__startswith=ACCOUNT_PREFIX).mock(return_value=httpx.Response(404))
        with pytest.raises(RiotIdNotFound):
            register_member(
                session,
                RiotClient(api_key, clock=clock, sleep=sleeper),
                "Missing#NA1",
                "na1",
                now_ms=NOW_MS,
                backfill_days=7,
            )


def test_register_member_maps_auth_error(session, api_key, clock, sleeper):
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(url__startswith=ACCOUNT_PREFIX).mock(return_value=httpx.Response(401))
        with pytest.raises(SignupUnavailable):
            register_member(
                session,
                RiotClient(api_key, clock=clock, sleep=sleeper),
                "Anyone#NA1",
                "na1",
                now_ms=NOW_MS,
                backfill_days=7,
            )


def test_register_member_maps_unavailable(session, api_key, clock, sleeper):
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        route = router.get(url__startswith=ACCOUNT_PREFIX).mock(return_value=httpx.Response(503))
        with pytest.raises(SignupUnavailable):
            register_member(
                session,
                RiotClient(api_key, clock=clock, sleep=sleeper),
                "Anyone#NA1",
                "na1",
                now_ms=NOW_MS,
                backfill_days=7,
            )
        assert route.call_count == 5  # all retry attempts exhausted


def test_register_member_maps_unexpected_error(session, api_key, clock, sleeper):
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(url__startswith=ACCOUNT_PREFIX).mock(return_value=httpx.Response(400))
        with pytest.raises(SignupUnavailable):
            register_member(
                session,
                RiotClient(api_key, clock=clock, sleep=sleeper),
                "Anyone#NA1",
                "na1",
                now_ms=NOW_MS,
                backfill_days=7,
            )
