# To Claude
**Task:** T001 (Scaffold, config, DB models, and match parsing)
**Status:** done
**Report:** handoffs/reports/T001-report.md
**Updated:** 2026-09-28 17:50

## In one paragraph
Full scaffold delivered: uv/pyproject with the spec's deps and console script, `Settings` (pydantic-settings), DB layer (SQLite WAL + FK pragmas, dir creation), typed ORM models with the unique constraint and both indexes, Alembic with an initial migration that creates all three tables, and a pure parsing layer (`parse_match_summary`, `parse_member_game` with frozen dataclasses) plus a `parse-fixture` CLI. All 7 acceptance criteria pass: `uv sync`, 13 tests (every expected value verified against fixtures), ruff check + format clean, migration creates the three tables, CLI prints `"peak_attack_speed": 154`, no hardcoded keys, `.gitignore` complete.

## Needs Claude's attention
1. Nullability decision: all API-derived stat columns are nullable (Riot can omit fields, e.g. `challenges`); timeline fields nullable per spec. Confirm this is what T002 should expect.
2. `backfill_from_ms` made nullable — architecture implies it's set at join time; if it should be non-null, T003/T004 must compute it before insert.
3. Ruff excludes `tools/` because `phase1_probe.py` predates the formatter and I may not modify `tools/` — the only way to keep `ruff format --check .` clean. OK, or reformat it in a later task?
4. Alembic reads the DB URL from Settings in `migrations/env.py` (blank `sqlalchemy.url` in the ini) and reuses `db.make_engine` so migrations get WAL/FK pragmas — the standard interpretation of the spec's wording.
