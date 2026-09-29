"""SQLAlchemy 2.0 ORM models: members, matches, member_games.

Only registered members' data is stored. Non-Arena matches get a `matches`
row too (with `is_arena=false`) so they are never fetched again.
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    puuid: Mapped[str] = mapped_column(String(78), unique=True)
    game_name: Mapped[str] = mapped_column(String(64))
    tag_line: Mapped[str] = mapped_column(String(16))
    platform: Mapped[str] = mapped_column(String(8))
    created_at_ms: Mapped[int]
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_polled_at_ms: Mapped[int | None]
    backfill_from_ms: Mapped[int | None]


class Match(Base):
    __tablename__ = "matches"

    match_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    platform: Mapped[str] = mapped_column(String(8))
    queue_id: Mapped[int | None]
    game_mode: Mapped[str | None] = mapped_column(String(16))
    game_start_ms: Mapped[int | None]
    game_end_ms: Mapped[int | None]
    duration_s: Mapped[int | None]
    is_arena: Mapped[bool]
    is_valid: Mapped[bool]
    fetched_at_ms: Mapped[int]


class MemberGame(Base):
    """One row per (member, Arena match). Match stats and timeline stats are
    denormalized for fast weekly queries."""

    __tablename__ = "member_games"
    __table_args__ = (
        UniqueConstraint("match_id", "member_id", name="uq_member_games_match_member"),
        Index("ix_member_games_member_id_game_end_ms", "member_id", "game_end_ms"),
        Index("ix_member_games_game_end_ms", "game_end_ms"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    match_id: Mapped[str] = mapped_column(String(32), ForeignKey("matches.match_id"))

    # identity
    champion_name: Mapped[str] = mapped_column(String(32))
    champion_id: Mapped[int | None]
    placement: Mapped[int | None]
    subteam_id: Mapped[int | None]
    augments: Mapped[list[int]] = mapped_column(JSON, default=list)

    # match stats
    damage_to_champions: Mapped[int | None]
    physical_damage_to_champions: Mapped[int | None]
    magic_damage_to_champions: Mapped[int | None]
    true_damage_to_champions: Mapped[int | None]
    largest_crit: Mapped[int | None]
    damage_taken: Mapped[int | None]
    damage_mitigated: Mapped[int | None]
    total_heal: Mapped[int | None]
    heals_on_teammates: Mapped[int | None]
    shields_on_teammates: Mapped[int | None]
    cc_time: Mapped[int | None]
    largest_multikill: Mapped[int | None]
    penta_kills: Mapped[int | None]
    gold_earned: Mapped[int | None]
    damage_per_minute: Mapped[float | None]

    # timeline stats (absent when the timeline is unavailable)
    final_ap: Mapped[float | None]
    peak_ap: Mapped[float | None]
    final_ad: Mapped[float | None]
    peak_ad: Mapped[float | None]
    final_health_max: Mapped[float | None]
    peak_health_max: Mapped[float | None]
    final_armor: Mapped[float | None]
    final_mr: Mapped[float | None]
    final_attack_speed: Mapped[float | None]
    peak_attack_speed: Mapped[float | None]

    # denormalized
    game_end_ms: Mapped[int | None]
    duration_s: Mapped[int | None]
