"""`didyouhit` command line interface."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from didyouhit.config import get_settings
from didyouhit.db import get_session_factory
from didyouhit.ingest import add_member, ingest_all
from didyouhit.models import Member
from didyouhit.parsing import parse_match_summary, parse_member_game
from didyouhit.riot.client import RiotClient
from didyouhit.riot.errors import RiotAuthError, RiotNotFoundError


def _now_ms() -> int:
    return int(time.time() * 1000)


def _client_or_error() -> RiotClient | None:
    settings = get_settings()
    if settings.riot_api_key is None or not settings.riot_api_key.get_secret_value():
        print("RIOT_API_KEY is not set (put it in .env)", file=sys.stderr)
        return None
    return RiotClient(settings.riot_api_key.get_secret_value(), rate_limits=settings.rate_limits)


def _parse_fixture(args: argparse.Namespace) -> int:
    match = json.loads(Path(args.match_json).read_text())
    timeline = json.loads(Path(args.timeline_json).read_text())
    settings = get_settings()
    summary = parse_match_summary(match, min_duration_s=settings.min_game_duration_s)
    game = parse_member_game(match, timeline, args.puuid)
    print(
        json.dumps(
            {"summary": asdict(summary), "member_game": asdict(game) if game else None},
            indent=2,
        )
    )
    return 0


def _add_member(args: argparse.Namespace) -> int:
    client = _client_or_error()
    if client is None:
        return 2
    settings = get_settings()
    with get_session_factory()() as session:
        try:
            member = add_member(
                session,
                client,
                args.riot_id,
                args.platform,
                now_ms=_now_ms(),
                backfill_days=settings.backfill_days,
            )
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        except RiotNotFoundError:
            print("error: Riot ID not found", file=sys.stderr)
            return 1
        except RiotAuthError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        session.commit()
        print(f"member {member.id}: {member.game_name}#{member.tag_line} ({member.platform})")
    return 0


def _fmt_last_polled(ms: int | None) -> str:
    if ms is None:
        return "-"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(timespec="seconds")


def _members(args: argparse.Namespace) -> int:
    with get_session_factory()() as session:
        members = session.scalars(select(Member).order_by(Member.id)).all()
    for member in members:
        print(
            f"{member.id}\t{member.game_name}#{member.tag_line}\t{member.platform}\t"
            f"{'yes' if member.active else 'no'}\t{_fmt_last_polled(member.last_polled_at_ms)}"
        )
    return 0


def _ingest(args: argparse.Namespace) -> int:
    client = _client_or_error()
    if client is None:
        return 2
    settings = get_settings()
    with get_session_factory()() as session:
        try:
            stats = ingest_all(
                session,
                client,
                now_ms=_now_ms(),
                min_duration_s=settings.min_game_duration_s,
            )
        except RiotAuthError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
    print(
        f"members={stats.members} ids_listed={stats.ids_listed} "
        f"matches_fetched={stats.matches_fetched} timelines_fetched={stats.timelines_fetched} "
        f"member_games_created={stats.member_games_created} errors={stats.errors}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="didyouhit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_fixture = subparsers.add_parser(
        "parse-fixture", help="debug aid: parse a match + timeline fixture and print the records"
    )
    parse_fixture.add_argument("match_json")
    parse_fixture.add_argument("timeline_json")
    parse_fixture.add_argument("puuid")
    parse_fixture.set_defaults(func=_parse_fixture)

    add_member_parser = subparsers.add_parser(
        "add-member", help="look up a Riot ID and register it as a member"
    )
    add_member_parser.add_argument("riot_id", help='e.g. "GameName#TAG"')
    add_member_parser.add_argument("--platform", default="na1", help="platform, e.g. na1")
    add_member_parser.set_defaults(func=_add_member)

    members_parser = subparsers.add_parser("members", help="list all members")
    members_parser.set_defaults(func=_members)

    ingest_parser = subparsers.add_parser(
        "ingest", help="run one ingestion pass over all active members"
    )
    ingest_parser.set_defaults(func=_ingest)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
