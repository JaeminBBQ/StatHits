"""Tests for the rate-limited, retrying Riot API client (no real network)."""

from __future__ import annotations

import httpx
import pytest
import respx

from didyouhit.riot.client import RiotClient
from didyouhit.riot.errors import RiotAuthError, RiotNotFoundError, RiotUnavailableError
from didyouhit.riot.routing import PLATFORMS, account_route, match_route

MATCH_URL = "https://americas.api.riotgames.com/lol/match/v5/matches/NA1_1"
IDS_URL = "https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/fixture-puuid-01/ids"


def make_client(api_key: str, clock, sleeper, **kwargs) -> RiotClient:
    return RiotClient(api_key, http=httpx.Client(), clock=clock, sleep=sleeper, **kwargs)


def test_429_sleeps_retry_after_then_succeeds(api_key, clock, sleeper):
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(MATCH_URL).mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "3"}),
                httpx.Response(200, json={"info": {"gameMode": "CHERRY"}}),
            ]
        )
        client = make_client(api_key, clock, sleeper)
        match = client.get_match("NA1_1", "na1")
    assert match["info"]["gameMode"] == "CHERRY"
    assert sleeper.sleeps == [3.0]
    assert client.calls == 2


def test_two_503s_back_off_then_succeed(api_key, clock, sleeper):
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(MATCH_URL).mock(
            side_effect=[httpx.Response(503), httpx.Response(503), httpx.Response(200, json={})]
        )
        client = make_client(api_key, clock, sleeper)
        assert client.get_match("NA1_1", "na1") == {}
    assert sleeper.sleeps == [1.0, 2.0]
    assert client.calls == 3


def test_five_503s_raise_unavailable(api_key, clock, sleeper):
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(MATCH_URL).mock(return_value=httpx.Response(503))
        client = make_client(api_key, clock, sleeper)
        with pytest.raises(RiotUnavailableError):
            client.get_match("NA1_1", "na1")
    assert sleeper.sleeps == [1.0, 2.0, 4.0, 8.0]
    assert client.calls == 5


def test_network_error_backs_off_then_succeeds(api_key, clock, sleeper):
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(MATCH_URL).mock(
            side_effect=[httpx.ConnectError("boom"), httpx.Response(200, json={"ok": True})]
        )
        client = make_client(api_key, clock, sleeper)
        assert client.get_match("NA1_1", "na1") == {"ok": True}
    assert sleeper.sleeps == [1.0]
    assert client.calls == 2


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (404, RiotNotFoundError),
        (401, RiotAuthError),
        (403, RiotAuthError),
        (503, RiotUnavailableError),
    ],
)
def test_error_statuses_and_secret_hygiene(api_key, clock, sleeper, caplog, status, error_type):
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(MATCH_URL).mock(return_value=httpx.Response(status))
        client = make_client(api_key, clock, sleeper)
        with pytest.raises(error_type) as exc_info:
            client.get_match("NA1_1", "na1")
    exception = exc_info.value
    assert api_key not in str(exception)
    assert api_key not in repr(exception)
    assert api_key not in caplog.text
    if isinstance(exception, RiotAuthError):
        assert str(exception) == "Riot API key rejected or expired (HTTP 4xx)"
    if isinstance(exception, RiotUnavailableError):
        assert "/lol/match/v5/matches/NA1_1" in str(exception)
        assert "503" in str(exception)


def test_rate_limiter_sleeps_before_third_call(api_key, clock, sleeper):
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(MATCH_URL).mock(return_value=httpx.Response(200, json={}))
        client = make_client(api_key, clock, sleeper, rate_limits="2:1")
        for _ in range(3):
            client.get_match("NA1_1", "na1")
    assert sleeper.sleeps == pytest.approx([1.05])
    assert client.calls == 3


def test_iter_match_ids_paginates(api_key, clock, sleeper):
    page1 = [f"NA1_{i}" for i in range(100)]
    page2 = [f"NA1_{100 + i}" for i in range(100)]
    page3 = [f"NA1_{200 + i}" for i in range(37)]
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        route = router.get(url__startswith=IDS_URL).mock(
            side_effect=[
                httpx.Response(200, json=page1),
                httpx.Response(200, json=page2),
                httpx.Response(200, json=page3),
            ]
        )
        client = make_client(api_key, clock, sleeper)
        ids = list(client.iter_match_ids("fixture-puuid-01", "na1", start_time_s=1_700_000_000))
        assert route.call_count == 3
        assert router.calls[1].request.url.params["start"] == "100"
        assert router.calls[2].request.url.params["start"] == "200"
        assert router.calls[0].request.url.params["startTime"] == "1700000000"
    assert ids == page1 + page2 + page3
    assert len(ids) == 237
    assert client.calls == 3


def test_get_account_url_encodes_riot_id(api_key, clock, sleeper):
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        route = router.get(
            url__startswith="https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
        ).mock(
            return_value=httpx.Response(
                200, json={"puuid": "fixture-puuid-01", "gameName": "Na Me", "tagLine": "TA G"}
            )
        )
        client = make_client(api_key, clock, sleeper)
        account = client.get_account("na me", "ta g", "na1")
        assert route.call_count == 1
        raw_path = router.calls[0].request.url.raw_path.decode()
        assert raw_path.endswith("/by-riot-id/na%20me/ta%20g")
    assert account["puuid"] == "fixture-puuid-01"


def test_routing_map():
    assert (account_route("na1"), match_route("na1")) == ("americas", "americas")
    assert (account_route("oc1"), match_route("oc1")) == ("asia", "sea")
    assert (account_route("euw1"), match_route("euw1")) == ("europe", "europe")
    assert len(PLATFORMS) == 15


def test_unknown_platform_raises():
    with pytest.raises(ValueError):
        account_route("xx1")
    with pytest.raises(ValueError):
        match_route("xx1")
