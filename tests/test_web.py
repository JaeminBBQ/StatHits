"""Web tests: routes and rendering, the join flow, and the ingest loop.

Everything runs offline: `DATABASE_URL` points at the in-memory DB (see
conftest), the Riot API and the alert webhook are mocked with respx, and the
app's clock is pinned to a fixed Wednesday so week boundaries are stable.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from didyouhit.config import Settings
from didyouhit.models import Base, Member, MemberGame
from didyouhit.parsing import parse_member_game
from didyouhit.riot.client import RiotClient
from didyouhit.riot.errors import RiotAuthError
from didyouhit.web.app import create_app
from didyouhit.web.formatting import (
    board_value,
    format_date,
    format_dt,
    ordinal,
    reset_countdown,
)
from didyouhit.web.ingest_loop import (
    AUTH_FAILURE_ALERT,
    RECOVERED_ALERT,
    ingest_loop,
    run_ingest_once,
)
from didyouhit.weeks import week_bounds, week_label, week_start_ms

FIXTURES = Path(__file__).parent / "fixtures"
LA = "America/Los_Angeles"
HOUR_MS = 3_600_000
DAY_MS = 86_400_000
FAKE_API_KEY = "RGAPI-00000000-0000-0000-0000-000000000000"
ARENA_MATCH_ID = "NA1_5638612201"
ARENA_MATCH_URL = f"https://americas.api.riotgames.com/lol/match/v5/matches/{ARENA_MATCH_ID}"
ARENA_TIMELINE_URL = f"{ARENA_MATCH_URL}/timeline"
ACCOUNT_PREFIX = "https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
WEBHOOK_URL = "https://discord.example/api/webhooks/123"

FOOTER = "isn't endorsed by Riot Games"
BANNED_WORDS = re.compile(r"\b(rank|tier|mmr)", re.IGNORECASE)


def local_ms(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> int:
    return int(datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(LA)).timestamp() * 1000)


# A Wednesday, mid-week, so the seeded weeks are 2026-09-28 (current) and
# 2026-09-21 (last) no matter what wall-clock day the tests run on.
NOW_MS = local_ms(2026, 9, 30, 17)


def _fixed_now() -> int:
    return NOW_MS


def add_member(session_factory, puuid: str, game_name: str, *, active: bool = True) -> None:
    with session_factory() as session:
        session.add(
            Member(
                puuid=puuid,
                game_name=game_name,
                tag_line="NA1",
                platform="na1",
                created_at_ms=local_ms(2026, 9, 1),
                active=active,
                last_polled_at_ms=None,
                backfill_from_ms=1_000_000_000_000,
            )
        )
        session.commit()


def seed_demo_data(session_factory) -> None:
    """Two members with games in the current and last week, plus one XSS-name member.

    The fixture member's row reuses the parsed 1750 fixture so one row has
    realistic values (damage 53,976, AP 1,028, augments 205/65/45/93); only its
    game end time is moved into the fixed current week.
    """
    with session_factory() as session:
        member1 = Member(
            puuid="fixture-puuid-01",
            game_name="Fixture",
            tag_line="NA1",
            platform="na1",
            created_at_ms=local_ms(2026, 9, 1),
            active=True,
            last_polled_at_ms=None,
            backfill_from_ms=1_000_000_000_000,
        )
        member2 = Member(
            puuid="fixture-puuid-02",
            game_name="Beta",
            tag_line="NA1",
            platform="na1",
            created_at_ms=local_ms(2026, 9, 1),
            active=True,
            last_polled_at_ms=None,
            backfill_from_ms=1_000_000_000_000,
        )
        member3 = Member(
            puuid="fixture-puuid-03",
            game_name="<script>x</script>",
            tag_line="NA1",
            platform="na1",
            created_at_ms=local_ms(2026, 9, 1),
            active=True,
            last_polled_at_ms=None,
            backfill_from_ms=1_000_000_000_000,
        )
        session.add_all([member1, member2, member3])
        session.flush()

        current_start = week_start_ms(NOW_MS, LA)
        last_start = week_bounds(current_start - 1, LA)[0]

        match = json.loads((FIXTURES / "match_1750_NA1_5638612201.json").read_text())
        timeline = json.loads((FIXTURES / "timeline_1750_NA1_5638612201.json").read_text())
        game = parse_member_game(match, timeline, "fixture-puuid-01")
        assert game is not None
        fields = asdict(game)
        fields.pop("match_id")
        fields["game_end_ms"] = current_start + HOUR_MS
        session.add(MemberGame(member_id=member1.id, match_id=ARENA_MATCH_ID, **fields))

        session.add(
            MemberGame(
                member_id=member2.id,
                match_id="M-CURRENT",
                champion_name="Chogath",
                placement=1,
                augments=[1, 2, 3],
                game_end_ms=current_start + 2 * HOUR_MS,
                duration_s=1200,
                peak_ap=2000.0,
                damage_to_champions=9000,
                peak_health_max=8000.0,
                largest_crit=700,
                cc_time=56,
            )
        )
        session.add(
            MemberGame(
                member_id=member2.id,
                match_id="M-LAST",
                champion_name="TwistedFate",
                placement=1,
                augments=[4, 5],
                game_end_ms=last_start + HOUR_MS,
                duration_s=1500,
                peak_ap=1500.0,
                damage_to_champions=45000,
                peak_health_max=6000.0,
                largest_crit=500,
                cc_time=30,
            )
        )
        session.commit()


@pytest.fixture()
def web_settings(monkeypatch):
    """Pinned clock + fully explicit settings so the real .env can't leak in."""
    monkeypatch.setattr("didyouhit.web.app._now_ms", _fixed_now)
    return Settings(
        database_url="sqlite://",
        ingest_enabled=False,
        invite_code="sesame",
        alert_webhook_url=None,
    )


@pytest.fixture()
def web_client(web_settings):
    app = create_app(web_settings)
    Base.metadata.create_all(app.state.engine)
    seed_demo_data(app.state.session_factory)
    with TestClient(app) as client:
        yield client


def test_home_page(web_client):
    response = web_client.get("/")
    assert response.status_code == 200
    text = response.text
    assert "2026-09-28" in text
    assert "Resets in 4d 7h" in text
    for heading in ("Big numbers", "Damage &amp; utility", "Per minute", "This week&#39;s totals"):
        assert heading in text, heading
    assert "53,976" in text  # fixture damage, thousands separator
    assert "2,227" in text  # fixture damage per minute, integer
    assert "1,028" in text  # fixture peak AP
    assert "2,000" in text  # member 2's peak AP
    assert "Fixture#NA1" in text
    assert "Beta#NA1" in text
    assert "Heimerdinger" in text
    assert "Chogath" in text


def test_weeks_page(web_client):
    response = web_client.get("/weeks")
    assert response.status_code == 200
    text = response.text
    assert "/weeks/2026-09-21" in text
    assert "45,000" in text  # last week's damage winner, formatted
    assert "TwistedFate" in text
    assert "Beta#NA1" in text
    assert "2026-09-28" not in text  # the current week is not a past week


def test_week_detail_page(web_client):
    response = web_client.get("/weeks/2026-09-21")
    assert response.status_code == 200
    text = response.text
    assert "45,000" in text
    assert "Beta#NA1" in text
    assert "Big numbers" in text
    assert "TwistedFate" in text


def test_week_detail_empty_week_shows_empty_state(web_client):
    last_start = week_bounds(week_start_ms(NOW_MS, LA) - 1, LA)[0]
    empty_label = week_label(week_bounds(last_start - 1, LA)[0], LA)
    response = web_client.get(f"/weeks/{empty_label}")
    assert response.status_code == 200
    assert "No games yet this week." in response.text


def test_week_detail_bad_and_future_labels_404(web_client):
    assert web_client.get("/weeks/not-a-date").status_code == 404
    assert web_client.get("/weeks/2026-9-21").status_code == 404
    assert web_client.get("/weeks/2026-02-30").status_code == 404
    future_label = week_label(week_bounds(NOW_MS, LA)[1], LA)
    assert web_client.get(f"/weeks/{future_label}").status_code == 404


def test_member_page(web_client):
    response = web_client.get("/members/1")
    assert response.status_code == 200
    text = response.text
    assert "Fixture#NA1" in text
    assert "Member since Sep 1, 2026" in text
    assert "Sep 28, 1:00 AM" in text
    assert "Heimerdinger" in text
    assert "2nd place" in text
    assert "53,976" in text
    assert "1,028" in text
    assert "205, 65, 45, 93" in text


def test_member_page_unknown_and_inactive_404(web_client):
    assert web_client.get("/members/9999").status_code == 404
    with web_client.app.state.session_factory() as session:
        member = session.get(Member, 1)
        member.active = False
        session.commit()
    assert web_client.get("/members/1").status_code == 404


def test_member_name_is_escaped(web_client):
    response = web_client.get("/members/3")
    assert response.status_code == 200
    assert "&lt;script&gt;x&lt;/script&gt;" in response.text
    assert "<script>x</script>" not in response.text


def test_all_html_routes_have_footer_and_no_banned_words(web_client):
    paths = ["/", "/weeks", "/weeks/2026-09-21", "/members/1", "/members/3", "/join"]
    for path in paths:
        response = web_client.get(path)
        assert response.status_code == 200, path
        assert FOOTER in response.text, path
        assert not BANNED_WORDS.search(response.text), path
    for response in (web_client.get("/weeks/not-a-date"), web_client.get("/members/9999")):
        assert response.status_code == 404
        assert FOOTER in response.text
        assert not BANNED_WORDS.search(response.text)
    wrong_code = web_client.post(
        "/join", data={"riot_id": "NewGuy#NA1", "platform": "na1", "invite_code": "wrong"}
    )
    assert wrong_code.status_code == 403
    assert FOOTER in wrong_code.text
    assert not BANNED_WORDS.search(wrong_code.text)


def test_healthz(web_client):
    assert web_client.get("/healthz").json() == {"ok": True}


def test_join_closed_without_invite_code():
    app = create_app(Settings(database_url="sqlite://", ingest_enabled=False, invite_code=None))
    with TestClient(app) as client:
        response = client.get("/join")
    assert response.status_code == 200
    assert "Sign-ups are closed right now." in response.text
    assert "<form" not in response.text


def test_join_wrong_code(web_client):
    with respx.mock(assert_all_mocked=True):
        response = web_client.post(
            "/join", data={"riot_id": "NewGuy#NA1", "platform": "na1", "invite_code": "wrong"}
        )
    assert response.status_code == 403
    assert "That invite code isn&#39;t right." in response.text
    assert 'value="NewGuy#NA1"' in response.text  # the Riot ID is kept
    assert "<form" in response.text
    assert FAKE_API_KEY not in response.text


def test_join_success_redirects_and_creates_member(web_client):
    account = {"puuid": "fixture-puuid-04", "gameName": "NewGuy", "tagLine": "NA1"}
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(url__startswith=ACCOUNT_PREFIX).mock(
            return_value=httpx.Response(200, json=account)
        )
        response = web_client.post(
            "/join",
            data={"riot_id": "NewGuy#NA1", "platform": "na1", "invite_code": "sesame"},
            follow_redirects=False,
        )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.endswith("?joined=1") and "/members/" in location
    member_id = int(location.removeprefix("/members/").split("?")[0])
    with web_client.app.state.session_factory() as session:
        member = session.get(Member, member_id)
        assert member is not None
        assert member.game_name == "NewGuy"
        assert member.active is True
    page = web_client.get(location)
    assert page.status_code == 200
    assert "You're in!" in page.text
    assert "NewGuy#NA1" in page.text
    assert FAKE_API_KEY not in page.text


def test_join_not_found(web_client):
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(url__startswith=ACCOUNT_PREFIX).mock(return_value=httpx.Response(404))
        response = web_client.post(
            "/join",
            data={"riot_id": "Missing#NA1", "platform": "na1", "invite_code": "sesame"},
        )
    assert response.status_code == 404
    assert "We couldn&#39;t find that Riot ID in that region." in response.text
    assert 'value="Missing#NA1"' in response.text
    assert FAKE_API_KEY not in response.text


def test_join_auth_error_is_unavailable(web_client):
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(url__startswith=ACCOUNT_PREFIX).mock(return_value=httpx.Response(401))
        response = web_client.post(
            "/join",
            data={"riot_id": "Anyone#NA1", "platform": "na1", "invite_code": "sesame"},
        )
    assert response.status_code == 503
    assert "Sign-ups are temporarily unavailable. Try again later." in response.text
    assert FAKE_API_KEY not in response.text


def test_join_bad_format(web_client):
    with respx.mock(assert_all_mocked=True):
        response = web_client.post(
            "/join", data={"riot_id": "NoTag", "platform": "na1", "invite_code": "sesame"}
        )
    assert response.status_code == 400
    assert "Enter your Riot ID like Name#TAG." in response.text
    assert FAKE_API_KEY not in response.text


def test_board_value_formatting():
    assert board_value(53976, "dmg") == "53,976"
    assert board_value(1028.0, "AP") == "1,028"
    assert board_value(15741.0, "HP") == "15,741"
    assert board_value(56, "s") == "56s"
    assert board_value(2227.4, "dmg/min") == "2,227"
    assert board_value(2.75, "s/min") == "2.8"
    assert board_value(3, "games") == "3"
    assert board_value(1, "wins") == "1"
    assert board_value(None, "dmg") == "—"


def test_formatting_helpers():
    assert reset_countdown(3 * DAY_MS + 14 * HOUR_MS) == "3d 14h"
    assert format_dt(local_ms(2026, 9, 8, 21, 14), LA) == "Sep 8, 9:14 PM"
    assert format_date(local_ms(2026, 9, 8, 12), LA) == "Sep 8, 2026"
    assert ordinal(1) == "1st"
    assert ordinal(2) == "2nd"
    assert ordinal(3) == "3rd"
    assert ordinal(11) == "11th"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def ids_url(puuid: str) -> str:
    return f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"


def test_run_ingest_once_returns_stats(web_settings, session_factory, api_key, clock, sleeper):
    add_member(session_factory, "fixture-puuid-01", "Fixture")
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(url__startswith=ids_url("fixture-puuid-01")).mock(
            return_value=httpx.Response(200, json=[ARENA_MATCH_ID])
        )
        match_route = router.get(ARENA_MATCH_URL).mock(
            return_value=httpx.Response(200, json=load("match_1750_NA1_5638612201.json"))
        )
        timeline_route = router.get(ARENA_TIMELINE_URL).mock(
            return_value=httpx.Response(200, json=load("timeline_1750_NA1_5638612201.json"))
        )
        client = RiotClient(api_key, clock=clock, sleep=sleeper)
        stats = run_ingest_once(
            web_settings, session_factory=session_factory, client=client, now_ms=NOW_MS
        )
        assert match_route.call_count == 1
        assert timeline_route.call_count == 1
    assert stats.members == 1
    assert stats.ids_listed == 1
    assert stats.member_games_created == 1
    assert stats.errors == 0


class OutcomeClient:
    """Fake client whose listing plays back a script of outcomes."""

    def __init__(self, outcomes):
        self._outcomes = list(outcomes)

    def iter_match_ids(self, *args, **kwargs):
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return iter(outcome)


def test_loop_auth_streak_sends_one_alert_then_recovered(session_factory):
    settings = Settings(
        database_url="sqlite://",
        ingest_enabled=False,
        poll_interval_min=1,
        alert_webhook_url=WEBHOOK_URL,
    )
    add_member(session_factory, "fixture-puuid-01", "Fixture")
    stop_event = threading.Event()
    client = OutcomeClient([RiotAuthError(401), RiotAuthError(401), RiotAuthError(401), []])
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) >= 4:
            stop_event.set()

    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        webhook = router.post(WEBHOOK_URL).mock(return_value=httpx.Response(204))
        ingest_loop(
            stop_event,
            settings,
            session_factory=session_factory,
            client=client,
            now_ms=_fixed_now,
            sleep=fake_sleep,
        )
        assert webhook.call_count == 2

    payloads = [json.loads(call.request.content) for call in webhook.calls]
    assert payloads[0]["content"] == AUTH_FAILURE_ALERT
    assert payloads[1]["content"] == RECOVERED_ALERT
    assert sleeps == [60.0] * 4  # three failed passes plus the recovered one


def test_loop_survives_arbitrary_exception(session_factory):
    settings = Settings(
        database_url="sqlite://",
        ingest_enabled=False,
        poll_interval_min=1,
        alert_webhook_url=None,
    )
    add_member(session_factory, "fixture-puuid-01", "Fixture")
    stop_event = threading.Event()
    client = OutcomeClient([RuntimeError("boom"), []])
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) >= 2:
            stop_event.set()

    with respx.mock(assert_all_mocked=True):
        ingest_loop(
            stop_event,
            settings,
            session_factory=session_factory,
            client=client,
            now_ms=_fixed_now,
            sleep=fake_sleep,
        )
    assert sleeps == [60.0, 60.0]  # the crash did not kill the loop


def test_loop_without_client_does_not_start(session_factory):
    settings = Settings(database_url="sqlite://", ingest_enabled=False)
    stop_event = threading.Event()
    ingest_loop(stop_event, settings, session_factory=session_factory, client=None)
    assert not stop_event.is_set()


def test_app_without_ingest_starts_no_thread():
    app = create_app(Settings(database_url="sqlite://", ingest_enabled=False))
    with TestClient(app):
        assert not any(t.name == "didyouhit-ingest" for t in threading.enumerate())
