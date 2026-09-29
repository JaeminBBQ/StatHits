# Decision Log

Append-only. When a decision changes, add a new entry that supersedes the old one.

| # | Date | Decision | Why |
|---|---|---|---|
| D1 | 2026-09-27 | Stat leaderboards only; no skill rating, tiers, or "ranked" wording | Riot policy bans alternatives to official ranking systems |
| D2 | 2026-09-27 | No augment/Arena item win rates | Riot policy |
| D3 | 2026-09-27 | Official Riot API only; no client-side data (LCU, Live Client API, replays, uploader apps) | User ruled these out as ToS violations |
| D4 | 2026-09-27 | Pivot from ARAM: Mayhem to Arena | Mayhem is absent from match-v5 (not even listed); Arena has full data. See Phase 1 |
| D5 | 2026-09-28 | Identify Arena by `gameMode == "CHERRY"`, not a queue whitelist | Arena queue IDs 1740/1750 aren't in Riot's queues.json |
| D6 | 2026-09-28 | Stack: Python 3.12/uv, FastAPI + Jinja2, SQLite + SQLAlchemy + Alembic, httpx | Cheapest simple deploy; no JS build; implementer-friendly |
| D7 | 2026-09-28 | Store only members' derived stats; no raw JSON, no non-member identities | Minimizes privacy/policy surface; nothing needs it yet |
| D8 | 2026-09-28 | Week = Monday 00:00 `WEEK_TZ` (default America/Los_Angeles); games bucketed by end time | Friend group is on NA |
| D9 | 2026-09-28 | Ingestion polls unfiltered match IDs; non-Arena IDs are recorded as seen and skipped | Auto-discovers new Arena queues; never re-fetches |
| D10 | 2026-09-28 | "Peak" champion stats = max over timeline frames | Final-frame values under-report (attack speed 154 peak vs 123 final in real data) |
| D11 | 2026-09-28 | MVP = friend group on a personal key, invite-code sign-up; RSO later behind `signup.py` | Dev keys can't back public sites; RSO needs a production key |
| D12 | 2026-09-28 | Orchestration: Claude plans/reviews, DeepSeek implements via `handoffs/` md files, user relays | User's chosen workflow |
| D13 | 2026-09-28 | Name: didyouhit.gg (package `didyouhit`) | User's choice; no Riot trademarks |
| D14 | 2026-09-28 | Handoff via `handoffs/TO_DEEPSEEK.md` / `TO_CLAUDE.md`; the user relays "read X" and runs all git commits | User wants the relay to be one short sentence each way |
