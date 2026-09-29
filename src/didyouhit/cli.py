"""`didyouhit` command line interface."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from didyouhit.config import get_settings
from didyouhit.parsing import parse_match_summary, parse_member_game


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
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
