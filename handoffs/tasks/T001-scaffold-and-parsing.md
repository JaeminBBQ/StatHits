# T001: Scaffold, config, DB models, and match parsing

- **Owner:** DeepSeek
- **Depends on:** none
- **Size:** moderate

## Goal
Create the Python project skeleton and the pure parsing layer that turns a Riot match-v5 match + timeline JSON into the records we store. No network code yet (that's T002).

## Read first
1. `DEEPSEEK.md`
2. `docs/ARCHITECTURE.md` (Stack, Layout, Data model, Arena data facts)
3. `docs/PRODUCT.md` (stat definitions)
4. Skim `tools/phase1_probe.py` (reference only; its `timeline_stats` shows the peak/final logic)
5. Look at `tests/fixtures/` (real anonymized API responses)

## Scope
**Do:**
1. **Project setup** with `uv`:
   - `pyproject.toml` with `requires-python = ">=3.12"`, package `didyouhit` in `src/` layout, and a console script `didyouhit = "didyouhit.cli:main"`.
   - Runtime deps: `fastapi`, `jinja2`, `uvicorn`, `sqlalchemy>=2`, `alembic`, `httpx`, `pydantic-settings`. Dev deps: `pytest`, `respx`, `ruff`.
   - Ruff config: line length 100, target py312, default rules plus `I` (isort).
   - `uv python pin 3.12` so `uv sync` works on this machine (system python is 3.9).
2. **`config.py`**: a `Settings` class (pydantic-settings, reads `.env`) with: `app_name` (default `"didyouhit.gg"`), `riot_api_key` (SecretStr, optional, so tests run without it), `database_url` (default `sqlite:///./data/didyouhit.db`), `week_tz` (default `America/Los_Angeles`), `invite_code` (optional), `poll_interval_min` (15), `min_game_duration_s` (300), `rate_limits` (default `"20:1,100:120"`). Provide `get_settings()` (cached).
3. **`db.py`**: engine and session factory from `database_url`. For SQLite, enable WAL and foreign keys, and create the parent directory of the DB file if it's missing.
4. **`models.py`**: SQLAlchemy 2.0 typed ORM models for `members`, `matches` and `member_games`, exactly as in ARCHITECTURE.md → Data model. Store `augments` as a JSON column. Add indexes on `member_games(member_id, game_end_ms)` and `member_games(game_end_ms)`, plus the unique constraint `(match_id, member_id)`.
5. **Alembic**: set up `migrations/` (`alembic.ini` at repo root, reading the DB URL from `Settings`), with one initial migration that creates the three tables. Autogenerate is fine, but review the output.
6. **`parsing.py`**: pure functions with no DB or network access:
   - `parse_match_summary(match: dict) -> MatchSummary`: match_id, platform (lowercase `info.platformId`), queue_id, game_mode, game_start_ms, game_end_ms (`info.gameEndTimestamp`), duration_s (`info.gameDuration`; if > 100000 treat it as ms and divide by 1000), `is_arena` (`gameMode == "CHERRY"`), and `is_valid` per ARCHITECTURE.md (takes `min_duration_s` as a parameter).
   - `parse_member_game(match: dict, timeline: dict | None, puuid: str) -> MemberGameStats | None`: `None` if the PUUID isn't in the match. Maps every field in the `member_games` data model. `augments` = the non-zero values of `playerAugment1..6`, in order. `damage_per_minute` comes from `challenges` if present, otherwise `None`. Timeline stats: find this player's `participantId` from `match.info.participants`, read `frames[*].participantFrames[str(pid)].championStats`, and set final (last frame that has stats) and peak (max over frames). All timeline fields are `None` if there's no timeline.
   - Use `dataclasses` (frozen) or pydantic models for `MatchSummary` and `MemberGameStats`; your choice, but be consistent.
7. **`cli.py`**: a minimal `main()` with argparse and one subcommand, `didyouhit parse-fixture <match.json> <timeline.json> <puuid>`, which prints the parsed result as JSON. It's a debugging aid, and T002 adds real subcommands.
8. **Tests** (`tests/test_parsing.py`, `tests/test_models.py`):
   - Use `tests/fixtures/match_1750_NA1_5638612201.json` + its timeline with `fixture-puuid-01`. Assert: champion `Heimerdinger`, `damage_to_champions == 53976`, `magic_damage_to_champions == 52425`, `largest_crit == 0`, `damage_mitigated == 28788`, `cc_time == 56`, `gold_earned == 18674`, `augments == [205, 65, 45, 93]`, `final_ap == 1028`, `peak_ap == 1028`, `final_health_max == 4543`, `final_attack_speed == 123`, `peak_attack_speed == 154`.
   - Summary for that match: `is_arena` True, `is_valid` True, `queue_id == 1750`, `duration_s == 1454` (24:14).
   - `match_400_NA1_5438163867.json` → `is_arena` False.
   - A PUUID not in the match → `None`.
   - `timeline=None` → timeline fields are `None` and match fields are still populated.
   - A remake: copy the fixture in the test, set `gameEndedInEarlySurrender=True` on one participant, and assert `is_valid` is False. Also test the duration threshold.
   - The 1740 fixture parses for **every** participant (all 18 `fixture-puuid-NN`) without errors, and every placement is in 1..6.
   - Models: create all tables on an in-memory SQLite DB, insert a member + match + member_game, and check that the unique constraint rejects a duplicate `(match_id, member_id)`.
9. `README.md` at the repo root with a short project description and dev commands (`uv sync`, `uv run pytest`, `uv run ruff check .`, `uv run alembic upgrade head`). Keep it under 40 lines and point to `CLAUDE.md`/`DEEPSEEK.md`/`docs/`.

**Do not:**
- Write any HTTP/Riot API code, ingestion logic, board logic or web routes (T002–T004).
- Modify `tests/fixtures/*`, `tools/`, `docs/`, `CLAUDE.md` or `DEEPSEEK.md`.
- Open or read `.env`.
- Run `git commit` (the user commits).

## Acceptance criteria
All must pass from a clean checkout:
1. `uv sync` succeeds.
2. `uv run pytest -q` passes, with all tests above present.
3. `uv run ruff check .` is clean and `uv run ruff format --check .` is clean.
4. `DATABASE_URL=sqlite:///./data/t001-check.db uv run alembic upgrade head` creates the three tables. Then delete `data/t001-check.db`.
5. `uv run didyouhit parse-fixture tests/fixtures/match_1750_NA1_5638612201.json tests/fixtures/timeline_1750_NA1_5638612201.json fixture-puuid-01` prints JSON with `"peak_attack_speed": 154`.
6. `grep -rn "RIOT_API_KEY\|RGAPI" src tests` shows no hardcoded keys (reading the setting by name in config is fine).
7. `.gitignore` also covers `data/`, `.venv/`, `.ruff_cache/`, `.pytest_cache/` and `*.db`.

## Report
Write `handoffs/reports/T001-report.md` using `handoffs/REPORT_TEMPLATE.md`, overwrite `handoffs/TO_CLAUDE.md` (format in DEEPSEEK.md), and set T001 to `review` in `handoffs/BOARD.md`. Then tell the user: "Done. Tell Claude: read handoffs/TO_CLAUDE.md".
