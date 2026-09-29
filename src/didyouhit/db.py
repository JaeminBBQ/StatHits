"""Engine and session factory setup for SQLite-backed storage."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from didyouhit.config import get_settings


def _sqlite_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def make_engine(database_url: str) -> Engine:
    """Build an engine for `database_url`, preparing SQLite as needed.

    For SQLite file databases: creates the parent directory, enables WAL and
    foreign keys. For in-memory databases: uses a static pool so every
    connection sees the same database.
    """
    kwargs: dict[str, Any] = {}
    is_file_db = False
    if database_url.startswith("sqlite"):
        db_path = make_url(database_url).database
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            is_file_db = True
        else:
            kwargs["connect_args"] = {"check_same_thread": False}
            kwargs["poolclass"] = StaticPool
    engine = create_engine(database_url, **kwargs)
    if is_file_db:
        event.listen(engine, "connect", _sqlite_pragmas)
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@lru_cache
def get_engine() -> Engine:
    return make_engine(get_settings().database_url)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return make_session_factory(get_engine())
