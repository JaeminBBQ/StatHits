# To Claude
**Task:** T002 (riot-client-and-ingestion)
**Status:** done
**Report:** handoffs/reports/T002-report.md
**Updated:** 2026-09-28 17:53

## In one paragraph
Built the `riot/` package (platform routing copied from the Phase 1 probe, typed errors, `RiotClient` with injectable clock/sleep, sliding-window rate limits, Retry-After and backoff retries, `calls` counter), the ingestion service (`add_member`, `ingest_member`, `ingest_all`, summable `IngestStats`, per-match commits, 1h poll overlap, 7-day backfill), `backfill_days` in Settings, and the `add-member` / `members` / `ingest` CLI subcommands. All seven acceptance criteria pass: 40 tests (including every listed test and T001's), ruff check + format clean, the empty-key exit-2 path verified against a migrated throwaway DB, no hardcoded keys in `src`, and no changes to forbidden paths.

## Needs Claude's attention
1. Unexpected HTTP statuses (e.g. 400) raise a new base `RiotError` immediately and stop the run — alternatively they could be counted and skipped like `RiotUnavailableError`. Which do you want?
2. Backfill re-fetch failures (member joined after a match was ingested) count an error and retry next poll, rather than flipping the shared `matches` row to invalid. OK?
3. `add_member` on an existing member keeps the old `platform`/`backfill_from_ms`. Should re-adding reset the backfill window?
4. Client error messages include the member's own PUUID (it's in the request path). Allowed per the "no non-member PUUIDs" rule; flagging in case you'd rather strip it.
