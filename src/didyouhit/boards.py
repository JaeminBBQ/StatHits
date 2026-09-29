"""Weekly boards: definitions, pure computation, and the DB-loading layer.

Boards come from docs/PRODUCT.md -> "Weekly challenges". "Best single game"
boards take each member's best game; totals count over the week's rows.
Ties go to the earlier game. Wording here follows the policy from D1:
boards, positions and winners only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from didyouhit.models import Member, MemberGame
from didyouhit.weeks import week_bounds, week_label, week_start_ms

NO_GAME_END = 10**18  # sort key for a NULL game_end_ms: always last


@dataclass(frozen=True)
class GameRow:
    """The member_games fields the boards need, plus identity columns."""

    member_id: int
    match_id: str
    champion_name: str
    game_end_ms: int | None
    duration_s: int | None
    placement: int | None
    peak_ap: float | None
    peak_ad: float | None
    peak_health_max: float | None
    largest_crit: int | None
    damage_to_champions: int | None
    damage_mitigated: int | None
    heals_on_teammates: int | None
    shields_on_teammates: int | None
    cc_time: int | None


@dataclass(frozen=True)
class MemberInfo:
    id: int
    game_name: str
    tag_line: str
    active: bool

    @property
    def riot_id(self) -> str:
        return f"{self.game_name}#{self.tag_line}"


@dataclass(frozen=True)
class BoardEntry:
    position: int
    member_id: int
    riot_id: str
    value: float
    match_id: str | None
    champion_name: str | None
    game_end_ms: int | None


@dataclass(frozen=True)
class BoardDef:
    key: str
    label: str
    kind: str  # "single_game" or "total"
    getter: Callable[[GameRow], float | None] | None = None
    per_minute: bool = False
    unit: str = ""


def _ally_heal_shield(row: GameRow) -> float | None:
    """heals_on_teammates + shields_on_teammates; NULL half counts as 0."""
    if row.heals_on_teammates is None and row.shields_on_teammates is None:
        return None
    return (row.heals_on_teammates or 0) + (row.shields_on_teammates or 0)


def _per_minute(getter: Callable[[GameRow], float | None]) -> Callable[[GameRow], float | None]:
    """Wrap a getter into its per-minute form; skip rows without a duration."""

    def value(row: GameRow) -> float | None:
        raw = getter(row)
        if raw is None or not row.duration_s:
            return None
        return raw / (row.duration_s / 60)

    return value


BOARDS: tuple[BoardDef, ...] = (
    BoardDef("peak_ap", "Highest AP", "single_game", lambda row: row.peak_ap, unit="AP"),
    BoardDef("peak_ad", "Highest AD", "single_game", lambda row: row.peak_ad, unit="AD"),
    BoardDef(
        "peak_health", "Most max health", "single_game", lambda row: row.peak_health_max, unit="HP"
    ),
    BoardDef(
        "largest_crit", "Biggest crit", "single_game", lambda row: row.largest_crit, unit="dmg"
    ),
    BoardDef(
        "damage_to_champions",
        "Most damage",
        "single_game",
        lambda row: row.damage_to_champions,
        unit="dmg",
    ),
    BoardDef(
        "damage_mitigated",
        "Most damage mitigated",
        "single_game",
        lambda row: row.damage_mitigated,
        unit="dmg",
    ),
    BoardDef(
        "ally_heal_shield",
        "Most healing + shielding on allies",
        "single_game",
        _ally_heal_shield,
        unit="HP",
    ),
    BoardDef("cc_time", "Most CC time", "single_game", lambda row: row.cc_time, unit="s"),
    BoardDef(
        "damage_to_champions_per_min",
        "Most damage per minute",
        "single_game",
        _per_minute(lambda row: row.damage_to_champions),
        per_minute=True,
        unit="dmg/min",
    ),
    BoardDef(
        "damage_mitigated_per_min",
        "Most damage mitigated per minute",
        "single_game",
        _per_minute(lambda row: row.damage_mitigated),
        per_minute=True,
        unit="dmg/min",
    ),
    BoardDef(
        "ally_heal_shield_per_min",
        "Most healing + shielding per minute",
        "single_game",
        _per_minute(_ally_heal_shield),
        per_minute=True,
        unit="HP/min",
    ),
    BoardDef(
        "cc_time_per_min",
        "Most CC time per minute",
        "single_game",
        _per_minute(lambda row: row.cc_time),
        per_minute=True,
        unit="s/min",
    ),
    BoardDef("first_places", "First places", "total", unit="wins"),
    BoardDef("games_played", "Games played", "total", unit="games"),
)


def _end_key(game_end_ms: int | None) -> int:
    return game_end_ms if game_end_ms is not None else NO_GAME_END


def _single_game_entries(
    board: BoardDef, rows: Sequence[GameRow], members: Mapping[int, MemberInfo], *, limit: int
) -> list[BoardEntry]:
    assert board.getter is not None
    best: dict[int, tuple[float, GameRow]] = {}
    for row in rows:
        value = board.getter(row)
        if value is None:
            continue
        current = best.get(row.member_id)
        if current is None or (value, -_end_key(row.game_end_ms)) > (
            current[0],
            -_end_key(current[1].game_end_ms),
        ):
            best[row.member_id] = (value, row)
    ordered = sorted(
        best.items(),
        key=lambda item: (-item[1][0], _end_key(item[1][1].game_end_ms), item[0]),
    )
    return [
        BoardEntry(
            position=position,
            member_id=member_id,
            riot_id=members[member_id].riot_id,
            value=value,
            match_id=row.match_id,
            champion_name=row.champion_name,
            game_end_ms=row.game_end_ms,
        )
        for position, (member_id, (value, row)) in enumerate(ordered[:limit], start=1)
    ]


def _total_entries(
    board: BoardDef, rows: Sequence[GameRow], members: Mapping[int, MemberInfo], *, limit: int
) -> list[BoardEntry]:
    counts: dict[int, int] = {}
    reached_at: dict[int, int | None] = {}
    for row in sorted(rows, key=lambda row: _end_key(row.game_end_ms)):
        if board.key == "first_places" and row.placement != 1:
            continue
        counts[row.member_id] = counts.get(row.member_id, 0) + 1
        reached_at[row.member_id] = row.game_end_ms
    ordered = sorted(
        counts.items(),
        key=lambda item: (-item[1], _end_key(reached_at[item[0]]), item[0]),
    )
    return [
        BoardEntry(
            position=position,
            member_id=member_id,
            riot_id=members[member_id].riot_id,
            value=float(count),
            match_id=None,
            champion_name=None,
            game_end_ms=reached_at[member_id],
        )
        for position, (member_id, count) in enumerate(ordered[:limit], start=1)
    ]


def compute_boards(
    games: Sequence[GameRow], members: Mapping[int, MemberInfo], *, limit: int = 5
) -> dict[str, list[BoardEntry]]:
    """Compute every board over the given rows; inactive members are excluded."""
    active_rows = [row for row in games if members[row.member_id].active]
    result: dict[str, list[BoardEntry]] = {}
    for board in BOARDS:
        if board.kind == "total":
            result[board.key] = _total_entries(board, active_rows, members, limit=limit)
        else:
            result[board.key] = _single_game_entries(board, active_rows, members, limit=limit)
    return result


def _game_row(game: MemberGame) -> GameRow:
    return GameRow(
        member_id=game.member_id,
        match_id=game.match_id,
        champion_name=game.champion_name,
        game_end_ms=game.game_end_ms,
        duration_s=game.duration_s,
        placement=game.placement,
        peak_ap=game.peak_ap,
        peak_ad=game.peak_ad,
        peak_health_max=game.peak_health_max,
        largest_crit=game.largest_crit,
        damage_to_champions=game.damage_to_champions,
        damage_mitigated=game.damage_mitigated,
        heals_on_teammates=game.heals_on_teammates,
        shields_on_teammates=game.shields_on_teammates,
        cc_time=game.cc_time,
    )


def load_week(
    session: Session, start_ms: int, end_ms: int
) -> tuple[list[GameRow], dict[int, MemberInfo]]:
    """Member games with start_ms <= game_end_ms < end_ms, plus all members."""
    games = session.scalars(
        select(MemberGame).where(
            MemberGame.game_end_ms.is_not(None),
            MemberGame.game_end_ms >= start_ms,
            MemberGame.game_end_ms < end_ms,
        )
    ).all()
    members = {
        member.id: MemberInfo(member.id, member.game_name, member.tag_line, member.active)
        for member in session.scalars(select(Member)).all()
    }
    return [_game_row(game) for game in games], members


def weekly_boards(
    session: Session, ts_ms: int, tz: str, *, limit: int = 5
) -> dict[str, list[BoardEntry]]:
    """Boards for the week containing ts_ms."""
    start_ms, end_ms = week_bounds(ts_ms, tz)
    games, members = load_week(session, start_ms, end_ms)
    return compute_boards(games, members, limit=limit)


@dataclass(frozen=True)
class WeekSummary:
    start_ms: int
    label: str
    winners: dict[str, BoardEntry | None]


def past_weeks(session: Session, now_ms: int, tz: str) -> list[WeekSummary]:
    """Every week before the current one that has at least one game, newest first."""
    current_start = week_start_ms(now_ms, tz)
    game_ends = session.scalars(
        select(MemberGame.game_end_ms).where(MemberGame.game_end_ms.is_not(None))
    ).all()
    starts = sorted(
        {
            week_start_ms(end_ms, tz)
            for end_ms in game_ends
            if week_start_ms(end_ms, tz) < current_start
        },
        reverse=True,
    )
    summaries: list[WeekSummary] = []
    for start in starts:
        end = week_bounds(start, tz)[1]
        games, members = load_week(session, start, end)
        boards = compute_boards(games, members)
        winners = {key: entries[0] if entries else None for key, entries in boards.items()}
        summaries.append(WeekSummary(start, week_label(start, tz), winners))
    return summaries


def member_history(
    session: Session, member_id: int, *, limit: int = 50, before_ms: int | None = None
) -> list[GameRow]:
    """A member's games, newest first."""
    stmt = select(MemberGame).where(MemberGame.member_id == member_id)
    if before_ms is not None:
        stmt = stmt.where(MemberGame.game_end_ms < before_ms)
    stmt = stmt.order_by(MemberGame.game_end_ms.desc()).limit(limit)
    return [_game_row(game) for game in session.scalars(stmt).all()]
