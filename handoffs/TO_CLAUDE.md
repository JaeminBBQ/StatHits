# To Claude

**Task:** T004 (web-ui)
**Status:** done
**Report:** handoffs/reports/T004-report.md
**Updated:** 2026-09-28 18:49

## In one paragraph
Built the full server-rendered site (this week's boards with countdown, past weeks + winners, week detail, member pages, invite-code join, healthz, verbatim Riot footer on every HTML page including 404/403) plus the `INGEST_ENABLED`-gated background ingest loop with once-per-streak Discord alerts, and `didyouhit serve`. All acceptance criteria pass: 100 tests (32 new), ruff clean, banned-word grep empty, no forbidden paths touched, and a live serve against the real dev DB returns 200 with the footer and lists week 2026-09-07.

## Needs Claude's attention
1. `/join` says "Sign-ups are closed right now." until the user sets `INVITE_CODE` in `.env` (and `ALERT_WEBHOOK_URL` if they want key-death alerts — the existing Discord webhook can be reused).
2. The ingest loop runs one pass at startup, then every `POLL_INTERVAL_MIN` (deviation note 6 in the report).
3. Minor wording split: member page empty state is "No games yet." vs boards' "No games yet this week." (deliberate; see report).
4. `test_web.py` pins the app clock by monkeypatching `didyouhit.web.app._now_ms` — worth knowing when you review.
