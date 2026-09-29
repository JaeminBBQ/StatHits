# To DeepSeek

**Current task:** T004: Web UI, sign-up, and the background ingest loop
**Spec:** `handoffs/tasks/T004-web-ui.md`

1. Re-read `DEEPSEEK.md` (unchanged since T002, but the notification step is required).
2. Execute the spec.
3. When finished: write the report, overwrite `handoffs/TO_CLAUDE.md`, set T004 to `review`, **send the Discord notification**, and tell the user.

## Feedback on T002a + T003 (both accepted)
Claude re-ran everything (68 tests, lint, wording check) and read the code. Both are correct and clean. Answers to your questions:
1. When a backfill hits a 403, flipping the shared `matches` row to invalid is fine; boards read `member_games`, so other members' games are unaffected.
2. The per-minute labels and units are good as written.
3. `GameRow` stays as it is. The member page queries `member_games` directly (T004 spec §4).
4. T002 is marked done.

## Live run results (T005, done by Claude)
Ingestion worked against the real API: 23 Arena games, 0 errors, and an idempotent re-run. The data is in `data/didyouhit.db` for your manual checks (see the spec). Real values for scale, which matter for the layout: max health up to **15,741**, damage up to **116,687**, crits up to **1,538**, AP up to **1,384**. Make sure 6-digit numbers fit in the cards at 375px wide.
