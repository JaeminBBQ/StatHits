"""Direct member_games queries for the member page.

The member page needs more fields than the boards' `GameRow` carries, so it
reads `member_games` rows directly instead of going through `boards.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from didyouhit.models import Member, MemberGame


@dataclass(frozen=True)
class MemberGameRow:
    game_end_ms: int | None
    champion_name: str
    placement: int | None
    augments: list[int]
    damage_to_champions: int | None
    peak_ap: float | None
    peak_health_max: float | None
    largest_crit: int | None
    cc_time: int | None


def get_active_member(session: Session, member_id: int) -> Member | None:
    """The member with this id, or None if unknown or inactive."""
    member = session.get(Member, member_id)
    if member is None or not member.active:
        return None
    return member


def member_games(session: Session, member_id: int, *, limit: int = 50) -> list[MemberGameRow]:
    """A member's Arena games, newest first, up to `limit`."""
    rows = session.scalars(
        select(MemberGame)
        .where(MemberGame.member_id == member_id)
        .order_by(MemberGame.game_end_ms.desc())
        .limit(limit)
    ).all()
    return [
        MemberGameRow(
            game_end_ms=game.game_end_ms,
            champion_name=game.champion_name,
            placement=game.placement,
            augments=game.augments or [],
            damage_to_champions=game.damage_to_champions,
            peak_ap=game.peak_ap,
            peak_health_max=game.peak_health_max,
            largest_crit=game.largest_crit,
            cc_time=game.cc_time,
        )
        for game in rows
    ]
