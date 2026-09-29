# T002a Report

**Status:** done
**Implementer:** DeepSeek

## Summary
Fixed both bugs from Claude's T002 review. The poll cursor now advances only after every listed match is ingested or recorded as seen; any retryable failure holds it, so failed matches are re-listed on the next poll (this also fixes the backfill-skipping bug). Match-level 403s no longer abort ingestion: a 403 on match/timeline data triggers one cheap key re-check (`count=1` listing) — a dead key still aborts, a valid key means the match itself is forbidden and gets recorded as seen. 401s abort immediately with no re-check, and unexpected statuses (e.g. 400) are counted as retryable skips instead of killing the run.

## Files changed
- `src/didyouhit/ingest.py`:
  - `IngestStats` gained `retryable_failures` (counted in `__add__`).
  - `ingest_member` sets `last_polled_at_ms` only after all match IDs are processed and only if `retryable_failures == 0`; the early commit after listing is gone.
  - `_resolve_403`/`_check_key_after_403`: the 403 → key re-check flow, used by the match fetch, the timeline fetch and the backfill re-fetch.
  - 401 anywhere still raises `RiotAuthError` (listing 401/403 included); match/timeline `RiotUnavailableError` and unexpected `RiotError` now count as retryable; an unexpected `RiotError` on listing skips that member (cursor unchanged) and ingestion continues.
  - `_backfill_member_game` now takes the existing `Match` row and counts all its fetch failures as retryable (holding the cursor), per the answers in the spec.
- `tests/test_ingest.py`: the 7 new tests from the spec (cursor holds then advances, 404 advances the cursor, 403 valid key, 403 dead key, 401 no re-check, 400 on match, 400 on listing) plus updated expectations in `test_match_404_recorded_as_seen_and_not_retried`, `test_timeline_503s_skip_match_and_retry_next_poll` and `test_ingest_stats_sum`.

## Acceptance criteria
| Criterion | Result | Evidence (command + key output) |
|---|---|---|
| 1. `uv run pytest -q` passes, including tests 1–7 | pass | `68 passed in 0.63s` (46 before T002a: 6 new T002a tests + updated ones, 22 new T003 tests) |
| 2. `uv run ruff check .` and `uv run ruff format --check .` clean | pass | "All checks passed!" / "42 files already formatted" |
| 3. `git status --short` only shows `src/didyouhit/ingest.py`, `tests/`, `handoffs/` (plus T003's `pyproject.toml`/`uv.lock`/new modules) | pass | `git status` shows exactly: `pyproject.toml`, `uv.lock`, `src/didyouhit/{ingest,boards,weeks}.py`, `tests/{test_ingest,test_boards,test_weeks}.py`, and `handoffs/` files; nothing under `tests/fixtures/`, `tools/`, `docs/` |

## Deviations from the spec
1. **403 during a backfill re-fetch**: the spec's "record it as seen with `is_valid=False`" is applied to the existing `matches` row (flipping its `is_valid`), since there is no new row to insert. Counted in `errors`, not `retryable_failures`. An unresolved re-check during backfill is retryable and holds the cursor.
2. **Unresolved 403**: when the re-check call itself fails retryably (`RiotUnavailableError`/`RiotError`), the match is skipped without recording, `retryable_failures += 1` (and `errors += 1`) — the spec's "a match-level 403 that wasn't resolved" reading.
3. **Listing-level unexpected `RiotError`** counts in `errors` only, not `retryable_failures`: the member is skipped before the cursor logic runs, so the retryable counter (which gates cursor advancement) is moot there.

## Dependencies added
None.

## Questions / proposals for Claude
1. Deviation 1: is flipping the existing row's `is_valid` the right "record as seen" for a backfill 403, or should the row stay untouched and retry next poll?

## Known issues / follow-ups
- None.
