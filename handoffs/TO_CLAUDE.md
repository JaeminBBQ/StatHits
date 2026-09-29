# To Claude
**Task:** T002a (ingest-cursor-and-403-fix) + T003 (weeks-and-boards)
**Status:** done
**Report:** handoffs/reports/T002a-report.md, handoffs/reports/T003-report.md
**Updated:** 2026-09-28 18:19

## In one paragraph
T002a: the poll cursor now advances only after every listed match is ingested or recorded as seen — retryable failures (unavailable, unexpected statuses, failed backfill re-fetches, unresolved 403s) hold it, so failed matches are re-listed next poll; match-level 403s trigger a one-call key re-check that aborts only on a dead key and otherwise records the match as seen, while 401s abort immediately and listing 401/403 still abort. T003: DST-aware local-Monday week math (`weeks.py`, with `tzdata` added) and the full boards layer (`boards.py`): the PRODUCT.md board registry, pure `compute_boards` with best-game/tie/per-minute/total rules, and `load_week` / `weekly_boards` / `past_weeks` / `member_history`. All acceptance criteria for both tasks pass: 68 tests, ruff clean, no banned wording in `src`, no forbidden-path changes.

## Needs Claude's attention
1. T002a backfill-403: I apply "record as seen" to the existing `matches` row (flip `is_valid=False`). Is that right, or should the row stay untouched and retry next poll?
2. T003 per-minute labels/units are my wording ("Most damage per minute", dmg/min, HP/min, s/min) — right for the T004 UI?
3. `member_history` returns the board-focused `GameRow`; the member page also wants augments and full stats. Have T004 query `member_games` directly where it needs more, or widen `GameRow` now?
4. T002's board row still says "rework → T002a" — the rework is delivered here; mark T002 done when you're happy with T002a.
