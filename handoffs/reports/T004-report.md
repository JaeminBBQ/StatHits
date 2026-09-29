# T004 Report

**Status:** done
**Implementer:** DeepSeek

## Summary
Built the server-rendered web UI: this week's boards in four sections with a reset countdown, past weeks with per-board winners, week detail pages, member pages with the full Arena history, invite-code sign-up, and `/healthz`. The Riot footer is on every HTML page including 404/403. Added the in-process ingest loop (daemon thread, `INGEST_ENABLED`-gated) with once-per-streak Discord alerts for a rejected key, plus `didyouhit serve`. Jinja2 templates with autoescape on, hand-written dark CSS, no JS, no frameworks, no external assets.

## Files changed
- `src/didyouhit/config.py`: `ingest_enabled`, `alert_webhook_url`, `display_limit`.
- `src/didyouhit/signup.py` (new): `register_member` wrapping `ingest.add_member` with `InvalidRiotId` / `RiotIdNotFound` / `SignupUnavailable`; constant-time `check_invite_code`.
- `src/didyouhit/web/app.py` (new): `create_app(settings)`, all routes, one `RiotClient` per process (created in lifespan), one engine/session factory on `app.state`, HTML 404 handler.
- `src/didyouhit/web/ingest_loop.py` (new): `run_ingest_once` (logs summary), `ingest_loop` (never dies; auth-streak alerts; waits on `stop_event` so shutdown is immediate).
- `src/didyouhit/web/queries.py` (new): direct `member_games` reads for the member page.
- `src/didyouhit/web/formatting.py` (new): pure filters (thousands separators, per-minute rules, `56s`, `s/min` 1 decimal, `Xd Yh`, `Sep 8, 9:14 PM`).
- `src/didyouhit/web/templates/` (new): `base.html` (nav + verbatim footer), `_boards.html`, `index.html`, `weeks.html`, `week.html`, `member.html`, `join.html`, `error.html`.
- `src/didyouhit/web/static/style.css` (new): dark theme, custom properties, responsive card grid (1 col at 375px, no horizontal scroll), tabular-numeral hero values.
- `src/didyouhit/cli.py`: `didyouhit serve [--host] [--port]` (uvicorn; loop follows `INGEST_ENABLED`).
- `pyproject.toml` + `uv.lock`: `python-multipart` (form posts).
- `tests/test_web.py`, `tests/test_signup.py` (new): 32 new tests.

## Acceptance criteria
| Criterion | Result | Evidence (command + key output) |
|---|---|---|
| 1. `uv sync`; only new dep is `python-multipart` | pass | `uv sync` clean; `uv.lock` diff adds only python-multipart |
| 2. `uv run pytest -q` | pass | `100 passed` (68 existing + 32 new) |
| 3. `uv run ruff check .` + `ruff format --check .` | pass | `All checks passed!` / `53 files already formatted` |
| 4. Serve + curl against the real dev DB | pass | `curl -s localhost:8765/` → 200, contains "isn't endorsed by Riot Games"; `/weeks` shows "Week of 2026-08-31" and "Week of 2026-09-07"; server killed afterwards |
| 5. No banned wording in `src/didyouhit` | pass | `grep -rniE "\brank|ranked|\btier|mmr" src/didyouhit` → no matches (exit 1) |
| 6. No changes to forbidden paths | pass | `git status --short` touches only `pyproject.toml`, `uv.lock`, `src/didyouhit/{cli,config,signup,web}`, `tests/test_{web,signup}.py` |

## Deviations from the spec
1. `create_app` builds the engine/session factory itself from `settings.database_url` and exposes them on `app.state` — required so tests can create the schema and seed through the same engine the app reads.
2. The lifespan calls `ingest_loop(stop_event, settings, session_factory=..., client=...)` rather than a bare `ingest_loop(stop_event, settings)`, so the loop shares the app's engine and the one per-process client. `ingest_loop` still accepts the bare form (defaults build their own).
3. Join error statuses beyond the spec's 403: bad format → 400, Riot ID not found → 404, API unavailable → 503 (spec pinned only the wrong-code 403). "Keep what the user typed on error, except the invite code" is implemented.
4. `POST /join` while sign-ups are closed renders the closed state with 403 (spec only defined the GET).
5. Week label validation is a strict regex plus `week_from_label`'s `ValueError` (strptime rejects impossible dates like Feb 30, so no extra round-trip check was needed).
6. The ingest loop's wait is `stop_event.wait(interval)` by default, so shutdown wakes the thread immediately instead of sleeping out the full interval.
7. `/` shows `display_limit` (5) entries per board; `/weeks/{label}` uses limit 10 as specified. `BoardEntry.value` floats are displayed as integers everywhere except `s/min` (1 decimal), matching the formatting rules.

## Dependencies added
- `python-multipart` — required by FastAPI for `Form(...)` parsing of the join POST. Explicitly allowed by the spec.

## Questions / proposals for Claude
1. `/join` currently shows "Sign-ups are closed right now." because `INVITE_CODE` is not set in `.env`. The user should add one (and optionally `ALERT_WEBHOOK_URL`, which can reuse the existing Discord webhook) before inviting friends.
2. The ingest loop runs one pass immediately at startup, then every `POLL_INTERVAL_MIN`. Reasonable for the MVP; a small startup delay could be added if that ever matters.
3. The member page's empty state says "No games yet." while boards say "No games yet this week." — history is not week-scoped, so the wording differs on purpose; flagging in case you'd rather unify it.
4. Error pages reuse `error.html` for any HTTP error; 404s get "That page doesn't exist."

## Known issues / follow-ups
- Champion names are raw API names (`Chogath`, `TwistedFate`) per spec; T007 adds display names and augment names/icons.
- T006 (visual review) will exercise the layout, including 6-digit values in the hero numbers.
- If the Riot key dies while the loop is running, recovery alerting depends on `ALERT_WEBHOOK_URL` being set; without it, errors are log-only.

## To view the site locally
```
uv run didyouhit serve
```
then open http://127.0.0.1:8000 (boards, past weeks, members, join). No API calls happen unless `INGEST_ENABLED=true` or someone signs up.
