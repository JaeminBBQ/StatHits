"""Ingestion service: pull members' new matches from the Riot API into the DB.

Follows docs/ARCHITECTURE.md -> "Ingestion design". Only registered members'
data is ever stored; a match is committed as soon as it is processed so
partial progress survives a crash.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from didyouhit.models import Match, Member, MemberGame
from didyouhit.parsing import MatchSummary, parse_match_summary, parse_member_game
from didyouhit.riot.client import RiotClient
from didyouhit.riot.errors import RiotNotFoundError, RiotUnavailableError

logger = logging.getLogger("didyouhit.ingest")

DAY_MS = 86_400_000
POLL_OVERLAP_MS = 3_600_000
DEFAULT_BACKFILL_DAYS = 7


@dataclass
class IngestStats:
    """Counters for one ingestion pass; instances can be summed."""

    members: int = 0
    ids_listed: int = 0
    matches_fetched: int = 0
    timelines_fetched: int = 0
    member_games_created: int = 0
    errors: int = 0

    def __add__(self, other: IngestStats) -> IngestStats:
        return IngestStats(
            members=self.members + other.members,
            ids_listed=self.ids_listed + other.ids_listed,
            matches_fetched=self.matches_fetched + other.matches_fetched,
            timelines_fetched=self.timelines_fetched + other.timelines_fetched,
            member_games_created=self.member_games_created + other.member_games_created,
            errors=self.errors + other.errors,
        )


def add_member(
    session: Session,
    client: RiotClient,
    riot_id: str,
    platform: str,
    *,
    now_ms: int,
    backfill_days: int,
) -> Member:
    """Look up a Riot ID via account-v1 and store it as a (re)activated member."""
    game_name, separator, tag_line = riot_id.rpartition("#")
    if not separator or not game_name or not tag_line:
        raise ValueError(f'Riot ID must look like "Name#TAG", got {riot_id!r}')
    account = client.get_account(game_name, tag_line, platform)
    puuid = account["puuid"]
    existing = session.scalar(select(Member).where(Member.puuid == puuid))
    if existing is not None:
        existing.game_name = account.get("gameName") or existing.game_name
        existing.tag_line = account.get("tagLine") or existing.tag_line
        existing.active = True
        session.flush()
        return existing
    member = Member(
        puuid=puuid,
        game_name=account.get("gameName") or game_name,
        tag_line=account.get("tagLine") or tag_line,
        platform=platform,
        created_at_ms=now_ms,
        active=True,
        last_polled_at_ms=None,
        backfill_from_ms=now_ms - backfill_days * DAY_MS,
    )
    session.add(member)
    session.flush()
    return member


def _start_time_s(member: Member, *, now_ms: int) -> int:
    backfill_ms = (
        member.backfill_from_ms
        if member.backfill_from_ms is not None
        else now_ms - DEFAULT_BACKFILL_DAYS * DAY_MS
    )
    last_ms = member.last_polled_at_ms if member.last_polled_at_ms is not None else backfill_ms
    return max(backfill_ms, last_ms - POLL_OVERLAP_MS) // 1000


def _has_member_game(session: Session, member_id: int, match_id: str) -> bool:
    return (
        session.scalar(
            select(MemberGame.id).where(
                MemberGame.member_id == member_id, MemberGame.match_id == match_id
            )
        )
        is not None
    )


def _record_seen(
    session: Session,
    match_id: str,
    platform: str,
    summary: MatchSummary | None,
    *,
    now_ms: int,
) -> None:
    if summary is None:
        session.add(
            Match(
                match_id=match_id,
                platform=platform,
                queue_id=None,
                game_mode=None,
                game_start_ms=None,
                game_end_ms=None,
                duration_s=None,
                is_arena=False,
                is_valid=False,
                fetched_at_ms=now_ms,
            )
        )
        return
    session.add(
        Match(
            match_id=match_id,
            platform=summary.platform or platform,
            queue_id=summary.queue_id,
            game_mode=summary.game_mode,
            game_start_ms=summary.game_start_ms,
            game_end_ms=summary.game_end_ms,
            duration_s=summary.duration_s,
            is_arena=summary.is_arena,
            is_valid=summary.is_valid,
            fetched_at_ms=now_ms,
        )
    )


def _create_member_games(
    session: Session, match: dict, timeline: dict | None, match_id: str
) -> int:
    """Insert rows for every active member in this match; one fetch serves the group."""
    participants = {
        p.get("puuid")
        for p in (match.get("info") or {}).get("participants") or []
        if p.get("puuid")
    }
    created = 0
    for member in session.scalars(select(Member).where(Member.active.is_(True))).all():
        if member.puuid not in participants or _has_member_game(session, member.id, match_id):
            continue
        game = parse_member_game(match, timeline, member.puuid)
        if game is None:
            continue
        fields = asdict(game)
        fields.pop("match_id")
        session.add(MemberGame(member_id=member.id, match_id=match_id, **fields))
        created += 1
    return created


def _ingest_new_match(
    session: Session,
    client: RiotClient,
    member: Member,
    match_id: str,
    *,
    now_ms: int,
    min_duration_s: int,
    stats: IngestStats,
) -> None:
    try:
        match = client.get_match(match_id, member.platform)
    except RiotNotFoundError:
        _record_seen(session, match_id, member.platform, None, now_ms=now_ms)
        stats.errors += 1
        logger.warning("match %s: not found, recording as seen", match_id)
        session.commit()
        return
    except RiotUnavailableError:
        stats.errors += 1
        logger.warning("match %s: fetch failed, will retry next poll", match_id)
        return
    stats.matches_fetched += 1
    summary = parse_match_summary(match, min_duration_s=min_duration_s)
    timeline = None
    if summary.is_arena and summary.is_valid:
        try:
            timeline = client.get_timeline(match_id, member.platform)
        except RiotNotFoundError:
            summary = replace(summary, is_valid=False)
            stats.errors += 1
            logger.warning("timeline %s: not found, recording match as invalid", match_id)
        except RiotUnavailableError:
            stats.errors += 1
            logger.warning("timeline %s: fetch failed, will retry next poll", match_id)
            return
        else:
            stats.timelines_fetched += 1
    _record_seen(session, match_id, member.platform, summary, now_ms=now_ms)
    if summary.is_arena and summary.is_valid:
        stats.member_games_created += _create_member_games(session, match, timeline, match_id)
    session.commit()


def _backfill_member_game(
    session: Session,
    client: RiotClient,
    member: Member,
    match_id: str,
    *,
    stats: IngestStats,
) -> None:
    """The match was already ingested for someone else; re-fetch once for this member."""
    try:
        match = client.get_match(match_id, member.platform)
        timeline = client.get_timeline(match_id, member.platform)
    except (RiotNotFoundError, RiotUnavailableError):
        stats.errors += 1
        logger.warning("match %s: backfill fetch failed, will retry next poll", match_id)
        return
    stats.matches_fetched += 1
    stats.timelines_fetched += 1
    game = parse_member_game(match, timeline, member.puuid)
    if game is None:
        return
    fields = asdict(game)
    fields.pop("match_id")
    session.add(MemberGame(member_id=member.id, match_id=match_id, **fields))
    stats.member_games_created += 1
    session.commit()


def _ingest_match_id(
    session: Session,
    client: RiotClient,
    member: Member,
    match_id: str,
    *,
    now_ms: int,
    min_duration_s: int,
    stats: IngestStats,
) -> None:
    match_row = session.get(Match, match_id)
    if match_row is None:
        _ingest_new_match(
            session,
            client,
            member,
            match_id,
            now_ms=now_ms,
            min_duration_s=min_duration_s,
            stats=stats,
        )
    elif (
        match_row.is_arena
        and match_row.is_valid
        and not _has_member_game(session, member.id, match_id)
    ):
        _backfill_member_game(session, client, member, match_id, stats=stats)
    # else: already seen and covered, nothing to do


def ingest_member(
    session: Session,
    client: RiotClient,
    member: Member,
    *,
    now_ms: int,
    min_duration_s: int,
) -> IngestStats:
    """One poll for one member. `RiotAuthError` propagates; other errors are counted."""
    stats = IngestStats()
    try:
        match_ids = list(
            client.iter_match_ids(
                member.puuid, member.platform, start_time_s=_start_time_s(member, now_ms=now_ms)
            )
        )
    except RiotUnavailableError:
        stats.errors += 1
        logger.warning("member %s: match listing unavailable, will retry next poll", member.id)
        return stats
    stats.members = 1
    stats.ids_listed = len(match_ids)
    member.last_polled_at_ms = now_ms
    session.commit()
    for match_id in match_ids:
        _ingest_match_id(
            session,
            client,
            member,
            match_id,
            now_ms=now_ms,
            min_duration_s=min_duration_s,
            stats=stats,
        )
    logger.info(
        "member %s: %d ids listed, %d matches fetched, %d timelines fetched, "
        "%d games created, %d errors",
        member.id,
        stats.ids_listed,
        stats.matches_fetched,
        stats.timelines_fetched,
        stats.member_games_created,
        stats.errors,
    )
    return stats


def ingest_all(
    session: Session,
    client: RiotClient,
    *,
    now_ms: int,
    min_duration_s: int,
) -> IngestStats:
    """One poll over every active member."""
    total = IngestStats()
    members = session.scalars(
        select(Member).where(Member.active.is_(True)).order_by(Member.id)
    ).all()
    for member in members:
        total += ingest_member(
            session, client, member, now_ms=now_ms, min_duration_s=min_duration_s
        )
    return total
