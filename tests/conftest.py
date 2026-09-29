"""Shared test setup: offline settings and an in-memory database."""

from __future__ import annotations

import pytest

from didyouhit.config import get_settings
from didyouhit.db import get_engine, get_session_factory, make_engine, make_session_factory
from didyouhit.models import Base

FAKE_API_KEY = "RGAPI-00000000-0000-0000-0000-000000000000"


@pytest.fixture(autouse=True)
def _offline_settings(monkeypatch):
    """Point Settings at a fake key and an in-memory DB so tests never load the real .env."""
    monkeypatch.setenv("RIOT_API_KEY", FAKE_API_KEY)
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    yield
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@pytest.fixture()
def api_key() -> str:
    return FAKE_API_KEY


class FakeClock:
    """Monotonic clock that FakeSleep advances."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeSleep:
    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.sleeps: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.clock.now += seconds


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture()
def sleeper(clock) -> FakeSleep:
    return FakeSleep(clock)


@pytest.fixture()
def session_factory():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


@pytest.fixture()
def session(session_factory):
    with session_factory() as session:
        yield session
