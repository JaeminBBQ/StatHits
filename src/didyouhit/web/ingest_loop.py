"""The in-process background ingestion loop for the web server.

One daemon thread calls `run_ingest_once` every poll interval. The loop never
dies from an exception: a rejected API key logs an ERROR and sends one Discord
alert per failure streak (then one "recovered" alert on the next success);
anything else is logged and the loop carries on.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from threading import Event

import httpx
from sqlalchemy.orm import Session, sessionmaker

from didyouhit.config import Settings
from didyouhit.db import make_engine, make_session_factory
from didyouhit.ingest import IngestStats, ingest_all
from didyouhit.riot.client import RiotClient
from didyouhit.riot.errors import RiotAuthError

logger = logging.getLogger("didyouhit.ingest_loop")

AUTH_FAILURE_ALERT = (
    "didyouhit: Riot API key rejected (HTTP 4xx), ingestion paused until it works again"
)
RECOVERED_ALERT = "didyouhit: ingestion recovered"


def _now_ms() -> int:
    return int(time.time() * 1000)


def send_alert(settings: Settings, message: str) -> None:
    """POST one operational alert to the Discord webhook.

    Failures are swallowed with a warning; the webhook URL and the message
    itself never go to the logs.
    """
    webhook = settings.alert_webhook_url
    if webhook is None:
        return
    try:
        httpx.post(webhook.get_secret_value(), json={"content": message}, timeout=10.0)
    except httpx.HTTPError:
        logger.warning("alert webhook delivery failed; ignoring")


def run_ingest_once(
    settings: Settings,
    *,
    session_factory: sessionmaker[Session],
    client: RiotClient,
    now_ms: int,
) -> IngestStats:
    """One ingestion pass over every active member; logs the summary.

    `RiotAuthError` propagates so the loop can track failure streaks.
    """
    with session_factory() as session:
        stats = ingest_all(
            session, client, now_ms=now_ms, min_duration_s=settings.min_game_duration_s
        )
    logger.info(
        "ingestion pass: %d members, %d ids listed, %d matches fetched, %d timelines fetched, "
        "%d games created, %d errors, %d retryable",
        stats.members,
        stats.ids_listed,
        stats.matches_fetched,
        stats.timelines_fetched,
        stats.member_games_created,
        stats.errors,
        stats.retryable_failures,
    )
    return stats


def ingest_loop(
    stop_event: Event,
    settings: Settings,
    *,
    session_factory: sessionmaker[Session] | None = None,
    client: RiotClient | None = None,
    now_ms: Callable[[], int] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> None:
    """Run ingestion every `poll_interval_min` until `stop_event` is set.

    With the default `sleep` the loop waits on `stop_event`, so shutdown wakes
    it immediately. Tests inject `sleep`, `now_ms`, `client` and
    `session_factory`.
    """
    if client is None:
        logger.error("ingest loop disabled: RIOT_API_KEY is not set")
        return
    if session_factory is None:
        session_factory = make_session_factory(make_engine(settings.database_url))
    now = now_ms if now_ms is not None else _now_ms
    wait = sleep if sleep is not None else stop_event.wait
    interval = max(settings.poll_interval_min, 1) * 60.0
    streak = 0
    while not stop_event.is_set():
        try:
            run_ingest_once(settings, session_factory=session_factory, client=client, now_ms=now())
        except RiotAuthError:
            streak += 1
            logger.error("Riot API key rejected (HTTP 4xx), ingestion paused until it works again")
            if streak == 1:
                send_alert(settings, AUTH_FAILURE_ALERT)
        except Exception:
            logger.exception("ingestion pass crashed; continuing on the next interval")
        else:
            if streak:
                logger.info("ingestion recovered after %d failed passes", streak)
                send_alert(settings, RECOVERED_ALERT)
                streak = 0
        wait(interval)
