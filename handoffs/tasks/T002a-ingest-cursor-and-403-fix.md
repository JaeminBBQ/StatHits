# T002a: Fix the ingestion cursor and match-level 403 handling

- **Owner:** DeepSeek
- **Depends on:** T002
- **Size:** small

## Goal
Fix two correctness bugs Claude found in T002's review. The T002 tests pass but miss both of them.

## Read first
`DEEPSEEK.md`, `src/didyouhit/ingest.py`, `src/didyouhit/riot/{client,errors}.py`, `tests/test_ingest.py`

## Bug 1: the poll cursor advances past matches that failed
`ingest_member` sets `last_polled_at_ms = now_ms` right after listing, before the matches are processed. If a match fails with a retryable error and is older than the 1h overlap, the next poll's `startTime` is after it, so it's **never ingested**. This is likely during a new member's 7-day backfill.

**Fix:**
- Set `last_polled_at_ms = now_ms` **only after** all of that member's match IDs are processed, and only if **none of them hit a retryable failure**. Retryable failures are: `RiotUnavailableError`, an unexpected `RiotError`, a failed backfill re-fetch, and a match-level 403 that wasn't resolved (see Bug 2).
- Failures that are recorded (a 404 recorded as seen) don't block the cursor.
- Add `retryable_failures: int` to `IngestStats`, alongside `errors`, which still counts everything.

## Bug 2: a 403 on one match aborts everything, forever
Riot returns 403 for individual private matches (reported for ARAM: Mayhem). Today any 403 raises `RiotAuthError`, and `ingest_all` aborts. A single such match ID in someone's history would stop ingestion for all members on every poll.

**Fix, in `ingest.py`:**
- **401 anywhere:** still raise `RiotAuthError` and abort. A 401 always means a bad key.
- **403 on listing or on `get_account`:** still raise and abort, since listing is how we detect a dead key (expired dev keys return 403).
- **403 on `get_match` or `get_timeline`:** do **not** abort yet. Re-check the key with one cheap call: `client.get_match_ids(member.puuid, member.platform, start_time_s=None, count=1)`.
  - If that call raises `RiotAuthError`, the key is dead: re-raise and abort.
  - If it succeeds, the match itself is forbidden: record it as seen with `is_valid=False` (like a 404; `is_arena` from the match if you have it, otherwise False), log a WARNING `"match %s: forbidden (403), recording as seen"`, and count it in `errors`, not `retryable_failures`.
- **Unexpected `RiotError`** (e.g. HTTP 400) on a single match or timeline: count it as a retryable failure, skip the match, and continue. Don't record it, and don't abort.
- **Unexpected `RiotError` on listing:** count it, skip this member for this poll (cursor unchanged), and continue with the other members.

`RiotAuthError` already has `.status`, so use it to tell 401 from 403. Don't change the client's HTTP behavior.

## New tests (in `tests/test_ingest.py`)
1. **Cursor holds on failure:**
   - Member polled before with `last_polled_at_ms = T`. The listing returns two IDs; one ingests fine and the other's match request returns 503 ×5.
   - Result: `last_polled_at_ms` is still `T` and `retryable_failures == 1`.
   - On the next run (the 503 now returns 200), the failed match is ingested and `last_polled_at_ms` advances to the new `now_ms`.
2. **Cursor advances when the only failure is a 404:** a match 404 is recorded, and `last_polled_at_ms == now_ms`.
3. **Match-level 403 with a valid key:**
   - Match returns 403 and the key re-check (`count=1` listing) returns 200.
   - Result: no exception; the match is recorded with `is_valid=False`; the other matches in the same listing are still ingested; the cursor advances.
   - A second run doesn't request that match again.
4. **Match-level 403 with a dead key:** match returns 403 and the re-check returns 403, so `ingest_all` raises `RiotAuthError`.
5. **401 on a match:** raises `RiotAuthError` immediately, with no re-check call.
6. **Unexpected 400 on a match:** skipped, not recorded, `retryable_failures == 1`, cursor unchanged, other matches ingested.
7. **Unexpected 400 on one member's listing:** that member is skipped with the cursor unchanged, and the other member is still ingested.
8. Update any existing test whose expectations change, and say which ones in the report.

## Acceptance criteria
1. `uv run pytest -q` passes, including tests 1–7 above.
2. `uv run ruff check .` and `uv run ruff format --check .` are clean.
3. `git status --short` shows changes only in `src/didyouhit/ingest.py`, `src/didyouhit/riot/*` (only if needed), `tests/`, and `handoffs/` (report, BOARD, TO_CLAUDE).

## Answers to your T002 questions
1. Unexpected statuses: count and skip (Bug 2 above), never abort.
2. A failed backfill re-fetch counts and retries: correct. It's now a retryable failure that holds the cursor.
3. Re-adding a member keeps the old platform and backfill window: correct, keep it.
4. The member's own PUUID in error messages: acceptable. Keep logs at member **id** level as you did.

## Report
Write `handoffs/reports/T002a-report.md`, then continue straight on to **T003** (see `TO_DEEPSEEK.md`). Update `TO_CLAUDE.md` once, after T003, covering both tasks.
