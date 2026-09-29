# T003 Report

**Status:** done
**Implementer:** DeepSeek

## Summary
Built the week window math and the weekly boards. `weeks.py` computes DST-aware local-Monday week boundaries (167/168/169-hour weeks via zoneinfo), labels, and the reset countdown; `tzdata` is now a runtime dependency so slim Linux containers have time zone data. `boards.py` holds the `BOARDS` registry from PRODUCT.md (8 single-game boards, 4 per-minute variants, 2 totals), the pure `compute_boards` (best game per member, NULLs ignored, earlier-game tie rule, per-minute values, total counts with the reached-first tie rule, inactive members excluded, every key always present), and the DB layer (`load_week`, `weekly_boards`, `past_weeks`, `member_history`). 22 new tests cover the pure logic, the DST cases from the spec, and the DB layer including a real parsed 1750 fixture game.

## Files changed
- `pyproject.toml` / `uv.lock`: added `tzdata` (2026.4) — the only new dependency.
- `src/didyouhit/weeks.py`: `week_start_ms`, `week_bounds` (end = next local Monday 00:00, computed in local time so DST weeks come out 167/169h), `week_label`, `week_from_label`, `ms_until_reset`.
- `src/didyouhit/boards.py`: `GameRow`, `MemberInfo` (with `riot_id`), `BoardEntry`, `BoardDef`, `BOARDS` (keys/labels/units per PRODUCT.md), `_ally_heal_shield` (NULL half = 0, both NULL = NULL), `_per_minute` (skips `duration_s` NULL/0), pure `compute_boards`, and the DB layer: `load_week`, `weekly_boards`, `WeekSummary` + `past_weeks`, `member_history`.
- `tests/test_weeks.py`: 6 tests — Sunday/Monday boundary, label round-trip, the 169h fall-back week, the 168h/167h spring-forward weeks, a UTC week, and `ms_until_reset`.
- `tests/test_boards.py`: 16 tests — best-game dedup, limit, tie rule, NULL handling, ally-heal-shield NULLs, per-minute vs raw ordering, per-minute duration skip, first-places count + tie rule, games-played, inactive exclusion, every-key-present, banned-wording walk over `BOARDS`, and the DB tests (week filtering, `past_weeks`, `member_history`, realistic 1750 fixture game showing 53976 dmg and 1028 peak AP).

## Acceptance criteria
| Criterion | Result | Evidence (command + key output) |
|---|---|---|
| 1. `uv sync` succeeds, `tzdata` the only new dependency | pass | `uv sync` — "Installed 2 packages … + tzdata==2026.4"; diff of `pyproject.toml` adds only `"tzdata"` |
| 2. `uv run pytest -q` passes (all earlier + new tests) | pass | `68 passed in 0.63s` (46 before T003; 22 new) |
| 3. `uv run ruff check .` and `uv run ruff format --check .` clean | pass | "All checks passed!" / "42 files already formatted" |
| 4. No banned wording in `src/didyouhit` | pass | `grep -rniE "\brank|ranked|\btier|mmr|elo\b" src/didyouhit` → no matches (exit 1); a first draft docstring tripped this and was reworded |
| 5. No changes to forbidden paths | pass | `git status --short` shows only `pyproject.toml`, `uv.lock`, `src/didyouhit/{ingest,boards,weeks}.py`, `tests/` and `handoffs/` files |

## Deviations from the spec
1. **Deterministic final tiebreak**: when two entries tie on both value and `game_end_ms` (possible when two members share the same best match on a board, e.g. both crit 0), the lower `member_id` sorts first. The spec is silent; this keeps the order stable.
2. **`BoardEntry.game_end_ms` for totals** = the timestamp of the game that reached the count (the tie-break value), since the spec says `match_id`/`champion_name` are None for totals but still defines `game_end_ms` on the entry.
3. **`BOARDS` is an immutable tuple of frozen `BoardDef`s** with lambda getters; nothing mutable about the registry.
4. **Per-minute labels/units are my wording** where PRODUCT.md only says `*_per_min`: "Most damage per minute" (dmg/min), "Most damage mitigated per minute" (dmg/min), "Most healing + shielding per minute" (HP/min), "Most CC time per minute" (s/min). See question 1.
5. **`load_week` loads every member**, not just the ones with games, so `compute_boards` can apply the inactive-exclusion rule itself.

## Dependencies added
`tzdata` 2026.4 (runtime; from the spec).

## Questions / proposals for Claude
1. Are the per-minute labels and units (deviation 4) the wording you want on the boards UI (T004)?
2. `GameRow` carries only the fields the boards need; `member_history` therefore returns those same fields, not full rows. The member page (T004) also wants augments — should `member_history` return a richer row (e.g. augments + all stats) later, or will T004 query `member_games` directly where it needs more?

## Known issues / follow-ups
- `past_weeks` recomputes boards per week from the whole dataset; fine at friend-group scale, and the spec says to keep it simple.
- `compute_boards` assumes every `GameRow.member_id` is present in the `members` mapping (the DB layer always loads all members).
