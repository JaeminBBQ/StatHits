# To DeepSeek

**Current task:** T002: Riot API client, ingestion service, CLI
**Spec:** `handoffs/tasks/T002-riot-client-and-ingestion.md`

1. Re-read `DEEPSEEK.md`. It has **changed**: there's a new required step, the Discord notification via `tools/notify.py`.
2. Then execute the spec above.
3. When finished: write the report, overwrite `handoffs/TO_CLAUDE.md`, set T002 to `review` in `handoffs/BOARD.md`, **send the Discord notification**, and tell the user: "Done. Tell Claude: read handoffs/TO_CLAUDE.md".

## Feedback on T001 (accepted, nice work)
Claude re-ran every acceptance check, and all pass. Answers to your questions:
1. **Nullable API-derived columns:** yes, keep them. Board queries (T003) will ignore NULLs.
2. **`backfill_from_ms` nullable:** fine. `add_member` in T002 always sets it, and ingestion treats NULL as "now − 7 days".
3. **Ruff excluding `tools/`:** fine. `tools/` holds standalone stdlib scripts (now including `notify.py`) that run on system python; leave the exclusion in place.
4. **Alembic URL from Settings via `make_engine`:** correct interpretation, keep it.

## Notes from Claude
- **Tests must never load the real key.** `Settings` reads `.env` from the working directory, which is why the spec requires the autouse `conftest.py` that overrides `RIOT_API_KEY` and `DATABASE_URL` and clears the settings cache.
- The fixtures use the same pseudonyms (`fixture-puuid-01..18`) in every match file, so "two members in the same match" works directly with the 1750 fixture.
