# T002 Report

**Status:** done
**Implementer:** DeepSeek

## Summary
Built the Riot API access layer and the ingestion service. `riot/` holds the platform→route map copied from the Phase 1 probe, three typed errors (plus a base class), and a `RiotClient` with injectable clock/sleep, sliding-window rate limits, `Retry-After`/backoff retries and a `calls` counter; error messages are always built from method, path and status, never from the key or headers. `ingest.py` implements `add_member`, `ingest_member`, `ingest_all` and a summable `IngestStats` per the ARCHITECTURE ingestion design, with per-match commits and the spec's error policy. The CLI gained `add-member`, `members` and `ingest`, `Settings` gained `backfill_days`, and 27 new tests (40 total) cover everything in the spec, all mocked offline.

## Files changed
- `src/didyouhit/riot/__init__.py`: package marker.
- `src/didyouhit/riot/routing.py`: `PLATFORMS` (copied from `tools/phase1_probe.py`), `account_route`/`match_route` raising `ValueError` on unknown platforms.
- `src/didyouhit/riot/errors.py`: `RiotNotFoundError`, `RiotAuthError` (message exactly as specified), `RiotUnavailableError`, plus a `RiotError` base (see deviations).
- `src/didyouhit/riot/client.py`: `RiotClient` with injectable `http`/`clock`/`sleep`, `"20:1,100:120"` sliding-window rate limiter (+50ms slack), 429 `Retry-After` (default 10), 1/2/4/8s backoff on 5xx and `TransportError`, 5-attempt cap, `X-Riot-Token` + `User-Agent: didyouhit/0.1` headers, `get_account` (URL-encoded), `get_match_ids`, `iter_match_ids` (paginates by 100), `get_match`, `get_timeline`, `calls` counter.
- `src/didyouhit/ingest.py`: `add_member` (last-`#` split, canonical name/tag, reactivation instead of duplicate rows, `backfill_from_ms`), `_start_time_s` (1h overlap, 7-day default backfill), fresh-match and joined-later-backfill flows, per-match commits, `IngestStats` with `__add__`, `didyouhit.ingest` logger (INFO per member, WARNINGs on errors; never logs non-member PUUIDs).
- `src/didyouhit/config.py`: added `backfill_days: int = 7`.
- `src/didyouhit/cli.py`: kept `parse-fixture`; added `add-member "Name#TAG" [--platform na1]`, `members`, and `ingest` (prints `IngestStats`). Missing key → exit 2 with the exact required message; the key is never printed.
- `tests/conftest.py`: autouse fixture that sets the fake key, points `DATABASE_URL` at `sqlite://`, and clears the settings/db caches before and after each test; shared `session_factory`/`session` fixtures and `FakeClock`/`FakeSleep`.
- `tests/test_client.py`: all client tests from the spec plus network-error retry, exact auth message, pagination params and URL-encoding checks.
- `tests/test_ingest.py`: all ingest tests from the spec plus `IngestStats` summing, the 7-day default backfill, and bad-Riot-ID rejection.
- `tests/test_models.py`: removed its local `session_factory` fixture (now provided identically by `conftest.py`); tests unchanged.

## Acceptance criteria
| Criterion | Result | Evidence (command + key output) |
|---|---|---|
| 1. `uv sync` succeeds, deps unchanged from T001 | pass | `uv sync` — "Resolved 32 packages … Checked 31 packages"; `pyproject.toml`/`uv.lock` untouched (not in `git status`) |
| 2. `uv run pytest -q` passes, incl. every listed test; T001 tests still pass | pass | `40 passed in 0.42s` (13 T001 tests + 27 new) |
| 3. `uv run ruff check .` and `uv run ruff format --check .` clean | pass | "All checks passed!" / "35 files already formatted" |
| 4. `uv run didyouhit --help` lists the four subcommands | pass | usage shows `{parse-fixture,add-member,members,ingest}` |
| 5. Empty `RIOT_API_KEY` ingest exits 2 with the message | pass | `RIOT_API_KEY= DATABASE_URL=sqlite:///./data/t002-check.db uv run didyouhit ingest` → `RIOT_API_KEY is not set (put it in .env)`, `exit code: 2` (ran `alembic upgrade head` on that DB first; `data/t002-check.db*` deleted) |
| 6. No hardcoded keys in `src` | pass | `grep -rn "RGAPI-[0-9a-f]\{8\}-[0-9a-f]\{4\}" src` → no matches (exit 1); the fake key exists only in `tests/` |
| 7. No changes under `tests/fixtures/`, `tools/`, `docs/`, `CLAUDE.md`, `DEEPSEEK.md` | pass | `git status --short` shows only `src/` and `tests/` files from this task |

## Deviations from the spec
1. **Base `RiotError` + unexpected-status handling.** The spec names three error classes; I added a common `RiotError` base and made unexpected statuses (e.g. 400 — a client bug, so retrying is pointless) raise it immediately. It is not caught by ingestion, so it stops the run loudly. See question 1.
2. **Backfill refetch error policy.** The spec's error bullets describe the fresh-match flow. For the "match already seen, fill in this member" path, a 404/5xx on the re-fetch counts an error and leaves the rows untouched so the next poll retries, instead of flipping the shared `matches` row to `is_valid=False` (which would invalidate other members' data over one member's transient failure). See question 2.
3. **`last_polled_at_ms` is committed immediately after a successful listing**, before match processing — "set only if the listing succeeded" per spec. The 1h overlap guarantees unprocessed matches are re-listed after a crash.
4. **50ms rate-limit slack** beyond the window edge, matching `tools/phase1_probe.py`'s behavior (the spec's "copied from the probe" reference). The client test asserts `≈1.05s`.
5. **respx specifics** (test-only): listing routes use `url__startswith=` because respx 0.23 matches the full URL including query on `eq` lookups; mocks use `assert_all_called=False` because tests deliberately register routes that stay uncalled (e.g. the timeline on a non-Arena match); clients are built inside the mock context because respx's decorator starts mocking only after pytest resolves fixtures.
6. **`add_member` flushes but does not commit**; the CLI commits after it. Ingest owns its commits per the spec.

## Dependencies added
None. `respx` was already a dev dependency.

## Questions / proposals for Claude
1. Unexpected HTTP statuses (e.g. 400) raise the base `RiotError` immediately and stop the run. Alternative: count the error and continue like `RiotUnavailableError`. Which do you want?
2. Backfill refetch failures (deviation 2) retry on the next poll rather than marking the shared match invalid. OK?
3. `add_member` on an existing member updates name/tag/active only — `platform` and `backfill_from_ms` are kept as-is. Should re-adding also reset the backfill window (e.g. for a member who was inactive a long time)?
4. `get_match_ids`/`iter_match_ids` put the member's own PUUID in the URL, so client error messages contain it. Members' PUUIDs are loggable per the privacy rule ("never log PUUIDs of non-members"); flagging in case you'd rather strip it.

## Known issues / follow-ups
- `RiotClient` never closes its internal `httpx.Client` (when `http` isn't injected). Fine for one-shot CLI runs; the T004 loop should reuse one long-lived client anyway.
- The `calls` counter counts attempts, not successes — the spec's tests only rely on deltas, and this matches the Phase 1 probe.
