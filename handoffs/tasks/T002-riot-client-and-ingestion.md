# T002: Riot API client, ingestion service, CLI

- **Owner:** DeepSeek
- **Depends on:** T001 (done)
- **Size:** moderate–large

## Goal
Fetch members' new matches from the Riot API efficiently and store their Arena stats, following ARCHITECTURE.md → "Ingestion design". Everything must be testable offline with mocked HTTP. The first live run against the real API is T005 and is done by Claude, not you.

## Read first
1. `DEEPSEEK.md`
2. `docs/ARCHITECTURE.md`: Data model, Arena data facts, **Ingestion design**
3. `docs/COMPLIANCE.md`
4. The existing code: `src/didyouhit/{config,db,models,parsing,cli}.py` and `tests/`
5. `tools/phase1_probe.py`: the reference for routing, the rate limiter and `Retry-After` handling (don't import it; reimplement cleanly)

## Scope
**Do:**

### 1. `src/didyouhit/riot/routing.py`
- A `PLATFORMS` map copied from `tools/phase1_probe.py` (platform → (account route, match route)).
- `account_route(platform)` and `match_route(platform)`. An unknown platform raises `ValueError`.

### 2. `src/didyouhit/riot/client.py`
- `RiotClient(api_key: str, rate_limits: str = "20:1,100:120", *, http: httpx.Client | None = None, clock=time.monotonic, sleep=time.sleep)`. Injecting `clock` and `sleep` lets tests run without real waiting.
- Headers: `X-Riot-Token` and `User-Agent: didyouhit/0.1`.
- **Rate limiter:** a sliding window for every `count:seconds` pair in `rate_limits`, applied before every request.
- **Retries:**
  - `429`: sleep for `Retry-After` seconds (default 10 if the header is missing), then retry.
  - `500/502/503/504` and network errors (`httpx.TransportError`): back off (1s, 2s, 4s…), then retry.
  - Give up after 5 attempts by raising `RiotUnavailableError`.
- **Errors** (put them in `riot/errors.py`):
  - `RiotNotFoundError` for 404.
  - `RiotAuthError` for 401 and 403. Its message is "Riot API key rejected or expired (HTTP 4xx)".
  - `RiotUnavailableError` when retries are exhausted.
  - **No exception message, `repr` or log line may contain the API key or request headers.** Build your own messages from method, path and status. Never pass through `str(httpx exception)`.
- Methods (return parsed JSON):
  - `get_account(game_name, tag_line, platform)`: `GET https://{account_route}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}`, URL-encoded.
  - `get_match_ids(puuid, platform, *, start_time_s: int | None, start: int = 0, count: int = 100) -> list[str]`
  - `iter_match_ids(puuid, platform, *, start_time_s)`: paginates by 100 until a page comes back with fewer than 100 IDs.
  - `get_match(match_id, platform)` and `get_timeline(match_id, platform)`.
- Keep a `calls` counter, since the tests use it.

### 3. `src/didyouhit/ingest.py`
- `add_member(session, client, riot_id: str, platform: str, *, now_ms: int, backfill_days: int) -> Member`:
  - Parse `"Name#TAG"`, splitting on the last `#`; bad format raises `ValueError`.
  - Look up the account and store the canonical `gameName`/`tagLine` returned by the API.
  - `backfill_from_ms = now_ms - backfill_days * 86_400_000`.
  - If the PUUID already exists, reactivate that member and update the name/tag instead of inserting a duplicate.
- `ingest_member(session, client, member, *, now_ms, min_duration_s) -> IngestStats` and `ingest_all(session, client, *, now_ms, min_duration_s) -> IngestStats`, the latter covering all active members. `IngestStats` is a dataclass with `members`, `ids_listed`, `matches_fetched`, `timelines_fetched`, `member_games_created`, `errors`, and supports summing.
- Algorithm (ARCHITECTURE.md → Ingestion design):
  - `start_time_s = max(backfill_from_ms, (last_polled_at_ms or backfill_from_ms) - 3_600_000) // 1000`. If `backfill_from_ms` is None, treat it as `now_ms - 7 days`.
  - For each listed ID **not** in `matches`: fetch the match and parse the summary.
    - Non-Arena or invalid: insert the `matches` row only (no timeline fetch).
    - Arena and valid: fetch the timeline, insert the `matches` row, then insert `member_games` for **every active member** whose PUUID is in `info.participants`, skipping any (match, member) pair that already exists.
  - For each listed ID **already** in `matches` with `is_arena and is_valid` but no `member_games` row for this member: re-fetch the match and timeline once, and insert this member's row only.
  - Commit after each match, so partial progress survives a crash.
- **Error policy:**
  - Match or timeline `RiotNotFoundError`: record the match as seen with `is_valid=False` (and `is_arena` from the match if you have it, otherwise False), so it's never retried. Count it in `errors`.
  - `RiotUnavailableError` on a single match: skip it without recording (it'll be retried next poll), count it, and continue.
  - `RiotAuthError`: raise immediately and stop ingestion. A bad key affects everything.
  - On success, set `member.last_polled_at_ms = now_ms` only if the member's ID listing succeeded.
- Use the `logging` module (logger `didyouhit.ingest`) for one INFO summary line per member and WARNINGs for errors. Never log PUUIDs of non-members.

### 4. Settings
Add `backfill_days: int = 7` to `Settings`.

### 5. CLI subcommands
Keep `parse-fixture` and add:
- `didyouhit add-member "Name#TAG" [--platform na1]`: prints the member's id and Riot ID.
- `didyouhit members`: lists members (id, Riot ID, platform, active, last polled).
- `didyouhit ingest`: one pass over all active members, printing the `IngestStats` summary.

The CLI builds the client from `get_settings().riot_api_key`. If it's missing, exit with code 2 and the message "RIOT_API_KEY is not set (put it in .env)". Never print the key. The CLI uses `db.get_session_factory()`; the DB schema comes from Alembic (`uv run alembic upgrade head`), so the CLI doesn't call `create_all`.

### 6. Tests
Add `tests/conftest.py`, `tests/test_client.py` and `tests/test_ingest.py`.
- **`conftest.py`** (autouse):
  - Set env `RIOT_API_KEY=RGAPI-00000000-0000-0000-0000-000000000000`, **point `DATABASE_URL` at `sqlite://`**, and call `get_settings.cache_clear()` (and the db factory caches). This keeps the real `.env` key from ever loading during tests.
  - Provide an in-memory session fixture that uses `Base.metadata.create_all`.
- **Every HTTP test uses `respx`** with `assert_all_mocked=True`. No real network.
- **Client tests:**
  - A 429 with `Retry-After: 3` sleeps 3s (via the fake sleep) and then succeeds.
  - A 503 twice, then 200, succeeds with backoff sleeps.
  - Five 503s raise `RiotUnavailableError`.
  - 404 → `RiotNotFoundError`; 401 and 403 → `RiotAuthError`.
  - The rate limiter with `"2:1"` and a fake clock sleeps before the 3rd call.
  - `iter_match_ids` paginates: pages of 100 + 100 + 37 give 237 IDs over 3 calls.
  - **Secret hygiene:** for each error type, assert the fake key doesn't appear in `str(exc)`, `repr(exc)` or `caplog.text`.
  - The routing map is correct for `na1` (americas/americas), `oc1` (asia/sea) and `euw1` (europe/europe), and an unknown platform raises.
- **Ingest tests:** mock the endpoints with the fixtures from `tests/fixtures/`.
  - Two members (`fixture-puuid-01` and `fixture-puuid-02`) are both in the 1750 match. Listing returns that ID for both. Result: the match and timeline are fetched **once**, `member_games` has 2 rows, and stats match the parsing tests for member 01.
  - A normal game (400 fixture) produces a `matches` row with `is_arena=False`, **no timeline request**, and no `member_games`.
  - Running `ingest_all` a second time with the same listing does zero match or timeline fetches (check `client.calls` and the respx call counts).
  - A remake (fixture copied in the test with `gameEndedInEarlySurrender=True`) produces a `matches` row with `is_valid=False` and no `member_games`.
  - A member who joined later: ingest the 1750 match for member 01 only, then add member 03 and ingest. The match and timeline are re-fetched once, and member 03's row is created.
  - A match 404 is recorded as seen with `is_valid=False`, `errors == 1`, and not fetched on the next run.
  - A timeline 503 ×5 means the match is not recorded, `errors == 1`, and it's fetched again on the next run.
  - A 401 on listing raises `RiotAuthError` from `ingest_all`.
  - `add_member` stores the canonical name/tag and `backfill_from_ms`, and adding the same PUUID twice doesn't duplicate the member.
  - `start_time_s` for a member polled before uses a 1h overlap. Assert the `startTime` query param respx received.
  - **Privacy check:** after ingesting the 1750 match with one member, the DB contains no other participant's PUUID or name. Scan every text column of every table for `fixture-puuid-` values other than the member's own, and for `Player0`/`Player1` names.

**Do not:**
- Build the background polling loop, the web UI or board logic (T003/T004).
- Make real network calls in tests, or read `.env` directly.
- Modify `tests/fixtures/*`, `tools/`, `docs/`, `CLAUDE.md` or `DEEPSEEK.md`.
- Run `git commit`.

## Acceptance criteria
1. `uv sync` succeeds, and the new deps list is unchanged from T001 (`respx` is already a dev dep).
2. `uv run pytest -q` passes, including every test listed above; T001's tests still pass.
3. `uv run ruff check .` and `uv run ruff format --check .` are clean.
4. `uv run didyouhit --help` lists `parse-fixture`, `add-member`, `members` and `ingest`.
5. `RIOT_API_KEY= DATABASE_URL=sqlite:///./data/t002-check.db uv run didyouhit ingest` exits with code 2 and the "RIOT_API_KEY is not set" message. (Run `alembic upgrade head` on that DB first if needed, then delete `data/t002-check.db*`.)
6. `grep -rn "RGAPI-[0-9a-f]\{8\}-[0-9a-f]\{4\}" src` finds nothing (the test fake key lives only in `tests/`).
7. `git status --short` shows no changes under `tests/fixtures/`, `tools/`, `docs/`, `CLAUDE.md` or `DEEPSEEK.md`.

## Report
Write `handoffs/reports/T002-report.md`, overwrite `handoffs/TO_CLAUDE.md`, set T002 to `review` in `handoffs/BOARD.md`, run `python3 tools/notify.py --from deepseek --kind done "T002 finished: <one line>. Tell Claude: read handoffs/TO_CLAUDE.md"`, then tell the user: "Done. Tell Claude: read handoffs/TO_CLAUDE.md".
