# T003: Week windows and weekly boards

- **Owner:** DeepSeek
- **Depends on:** T001, T002a
- **Size:** moderate

## Goal
Compute each week's boards from `member_games`: the best single game per member, per-minute variants, and weekly totals, plus winners for past weeks. The logic lives in pure functions with a thin DB-loading layer, and it's all unit-tested. There's no web UI yet (that's T004).

## Read first
1. `DEEPSEEK.md`
2. `docs/PRODUCT.md` → **Weekly challenges** (board list, keys, labels, sources, tie rule)
3. `docs/DECISIONS.md` D8 (week definition)
4. `src/didyouhit/models.py`

## Scope
**Do:**

### 1. `src/didyouhit/weeks.py` (pure; uses `zoneinfo`)
- `week_start_ms(ts_ms: int, tz: str) -> int`: the UTC epoch ms of Monday 00:00 local time, for the week containing `ts_ms`.
- `week_bounds(ts_ms, tz) -> tuple[int, int]`: `[start, end)`, where `end` is the **next local Monday 00:00**. Across a DST change a week is 167 or 169 hours, so never add a fixed 7 days of milliseconds.
- `week_label(start_ms, tz) -> str`: the local Monday date, e.g. `"2026-09-28"`. `week_from_label(label, tz) -> int` is its inverse.
- `ms_until_reset(now_ms, tz) -> int`.
- Add the `tzdata` runtime dependency, so slim Linux containers have time zone data.

### 2. `src/didyouhit/boards.py`
**Definitions.** A `BOARDS` registry built from PRODUCT.md, holding for each board: `key`, `label`, `kind` (`"single_game"` or `"total"`), a value getter, `per_minute: bool`, and a `unit` for display (e.g. `"AP"`, `"dmg"`, `"s"`).
- **Single-game boards:** `peak_ap`, `peak_ad`, `peak_health`, `largest_crit`, `damage_to_champions`, `damage_mitigated`, `ally_heal_shield` (= `heals_on_teammates + shields_on_teammates`, treating a NULL half as 0 but NULL if both are NULL), and `cc_time`.
- **Per-minute variants:** `damage_to_champions_per_min`, `damage_mitigated_per_min`, `ally_heal_shield_per_min` and `cc_time_per_min`. The value is `raw / (duration_s / 60)`; skip rows where `duration_s` is NULL or 0.
- **Totals:** `first_places` (count of `placement == 1`) and `games_played`.

**Pure core.** `compute_boards(games: Sequence[GameRow], members: Mapping[int, MemberInfo], *, limit: int = 5) -> dict[str, list[BoardEntry]]`
- `GameRow` is a small frozen dataclass with the `member_games` fields the boards need, plus `match_id`, `champion_name` and `game_end_ms`.
- `MemberInfo` holds `id`, `game_name`, `tag_line` and `active`. Inactive members are excluded.
- `BoardEntry` holds `position` (1-based), `member_id`, `riot_id` (`"Name#TAG"`), `value` (float), `match_id` and `champion_name` (both None for totals), and `game_end_ms`.
- **Single-game boards:** each member appears at most once, with their best game. Games whose value is NULL are ignored. Sort by value descending. On equal values, the **earlier `game_end_ms` wins**.
- **Totals:** count over the rows given. Members with 0 don't appear. On equal counts, the member who **reached the count first** wins, i.e. the smaller `game_end_ms` of the game that brought them to that count.
- Return every board key, even when a board has no entries.

**DB layer.**
- `load_week(session, week_start_ms, week_end_ms) -> tuple[list[GameRow], dict[int, MemberInfo]]`: `member_games` with `week_start ≤ game_end_ms < week_end`. Games with a NULL `game_end_ms` are excluded.
- `weekly_boards(session, ts_ms, tz, *, limit=5)`: boards for the week containing `ts_ms`.
- `past_weeks(session, now_ms, tz) -> list[WeekSummary]`: every week **before** the current one that has at least one game, newest first. Each `WeekSummary` has `start_ms`, `label`, and `winners: dict[board_key, BoardEntry | None]` (the position-1 entry for each board). Find the weeks from the distinct `game_end_ms` values of the member games; keep it simple, since data is small.
- `member_history(session, member_id, *, limit=50, before_ms=None) -> list[GameRow]`: newest first. The member page (T004) needs it.

### 3. Wording
Use "board", "position", "winner" and "leaderboard" in code and labels. **Never** "rank", "ranked", "tier" or "MMR" (DEEPSEEK.md hard rule). Add a test that walks through `BOARDS` and checks that no label or key contains "rank" or "tier".

### 4. Tests
`tests/test_weeks.py` and `tests/test_boards.py`. The pure tests build `GameRow`s by hand; the DB tests use the in-memory session fixture.
- **Weeks** (tz `America/Los_Angeles`):
  - A game at Sunday 2026-10-04 23:59 local and one at Monday 2026-10-05 00:00 local fall in different weeks.
  - `week_label` round-trips.
  - The week of Mon 2026-10-26 (DST ends Sun 2026-11-01) is **169h** long.
  - The week of Mon 2026-03-09 (DST starts Sun 2026-03-08) is **168h**, because the change happens before that Monday. Also check that the week of Mon 2026-03-02 is **167h**.
  - Check at least one case with `tz="UTC"` too.
- **Boards:**
  - Each member appears once, with their best game.
  - The limit is respected.
  - A tie on value goes to the earlier game.
  - NULLs are ignored.
  - `ally_heal_shield` handles NULLs as specified.
  - Per-minute: a 10-minute game with 20,000 damage (2,000/min) beats a 30-minute game with 45,000 (1,500/min), while the raw board orders them the other way.
  - `duration_s` of 0 or NULL is skipped for per-minute boards.
  - `first_places`: counts and the tie rule.
  - Inactive members are excluded.
  - Every key is present even with no games.
- **DB:**
  - Ingest-like rows across two weeks, then check that `weekly_boards` only sees the right week.
  - `past_weeks` excludes the current week, orders newest first, and has correct winners.
  - `member_history` orders newest first and respects the limit.
  - One realistic test: insert the member_game produced by parsing the 1750 fixture for `fixture-puuid-01`, and check that `peak_ap` shows 1028 and `damage_to_champions` shows 53976 for that match.

**Do not:**
- Build web routes or templates (T004).
- Modify `tests/fixtures/*`, `tools/`, `docs/`, `CLAUDE.md` or `DEEPSEEK.md`.
- Run `git commit`.

## Acceptance criteria
1. `uv sync` succeeds, with `tzdata` as the only new dependency.
2. `uv run pytest -q` passes (all earlier tests plus everything above).
3. `uv run ruff check .` and `uv run ruff format --check .` are clean.
4. `grep -rniE "\brank|ranked|\btier|mmr|elo\b" src/didyouhit` finds nothing.
5. `git status --short` shows no changes to forbidden paths.

## Report
Write `handoffs/reports/T003-report.md`, overwrite `handoffs/TO_CLAUDE.md` **covering T002a and T003**, set both to `review` in `BOARD.md`, run `python3 tools/notify.py --from deepseek --kind done "T002a + T003 finished: <one line>. Tell Claude: read handoffs/TO_CLAUDE.md"`, then tell the user.
