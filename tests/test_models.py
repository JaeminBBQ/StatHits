"""Tests for the ORM models on an in-memory SQLite database."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from didyouhit.models import Match, Member, MemberGame


def test_all_tables_created(session_factory):
    with session_factory() as session:
        tables = set(inspect(session.get_bind()).get_table_names())
    assert {"members", "matches", "member_games"} <= tables


def test_insert_member_match_and_member_game(session_factory):
    with session_factory() as session:
        member = Member(
            puuid="fixture-puuid-01",
            game_name="GameName",
            tag_line="NA1",
            platform="na1",
            created_at_ms=1788938554862,
            last_polled_at_ms=None,
            backfill_from_ms=1788307200000,
        )
        match = Match(
            match_id="NA1_5638612201",
            platform="na1",
            queue_id=1750,
            game_mode="CHERRY",
            game_start_ms=1788937100798,
            game_end_ms=1788938554862,
            duration_s=1454,
            is_arena=True,
            is_valid=True,
            fetched_at_ms=1788938555000,
        )
        session.add_all([member, match])
        session.flush()
        session.add(
            MemberGame(
                member_id=member.id,
                match_id=match.match_id,
                champion_name="Heimerdinger",
                champion_id=74,
                placement=2,
                subteam_id=1,
                augments=[205, 65, 45, 93],
                damage_to_champions=53976,
                gold_earned=18674,
                final_ap=1028,
                peak_ap=1028,
                game_end_ms=match.game_end_ms,
                duration_s=match.duration_s,
            )
        )
        session.flush()


def test_unique_constraint_rejects_duplicate_match_member(session_factory):
    with session_factory() as session:
        member = Member(
            puuid="fixture-puuid-01",
            game_name="GameName",
            tag_line="NA1",
            platform="na1",
            created_at_ms=1,
            last_polled_at_ms=None,
            backfill_from_ms=1,
        )
        match = Match(
            match_id="NA1_1",
            platform="na1",
            is_arena=True,
            is_valid=True,
            fetched_at_ms=1,
        )
        session.add_all([member, match])
        session.flush()
        game = dict(member_id=member.id, match_id=match.match_id, champion_name="Heimerdinger")
        session.add(MemberGame(**game))
        session.flush()
        session.add(MemberGame(**game))
        with pytest.raises(IntegrityError):
            session.flush()
