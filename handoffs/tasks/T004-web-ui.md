# T004: Web UI, sign-up, and the background ingest loop

- **Owner:** DeepSeek
- **Depends on:** T002a, T003 (done)
- **Size:** large

## Goal
A server-rendered site: this week's boards, past weeks, member pages and invite-code sign-up, with the Riot footer on every page, plus the in-process ingestion loop. The user will review it visually afterwards (T006), so aim for clean and readable, not elaborate.

## Read first
1. `DEEPSEEK.md`
2. `docs/PRODUCT.md` (pages, boards) and `docs/COMPLIANCE.md` (the footer text is verbatim)
3. `docs/ARCHITECTURE.md` → Stack, Auth
4. `src/didyouhit/{boards,weeks,ingest,config,db}.py`

## Real data you can look at
`data/didyouhit.db` (gitignored) holds the owner's real data from Claude's live run (T005): 1 member, 23 Arena games from the weeks of 2026-08-31 and 2026-09-07. Use it for manual checks: `uv run didyouhit serve` and open the pages. **Tests must never use this file** (conftest already points `DATABASE_URL` at `sqlite://`). Champion names are raw API names (`Chogath`, `TwistedFate`); show them as-is for now, since T007 adds display names.

## Scope
**Do:**

### 1. Settings (`config.py`)
Add:
- `ingest_enabled: bool = False`: the loop only runs when this is true, so tests and dev servers don't hit the API by default.
- `alert_webhook_url: SecretStr | None = None`: optional Discord webhook for operational alerts.
- `display_limit: int = 5`.

### 2. `src/didyouhit/signup.py`: the swappable sign-up boundary (RSO replaces it later)
- `register_member(session, client, riot_id, platform, *, now_ms, backfill_days) -> Member` wraps `ingest.add_member`.
- Define errors the web layer can map to messages: `InvalidRiotId` (bad format), `RiotIdNotFound` (404), and `SignupUnavailable` (auth error, or the API is unavailable).
- `check_invite_code(given, expected) -> bool`: uses `hmac.compare_digest`, and returns False if `expected` is None or empty.

### 3. `src/didyouhit/web/`
- `app.py` with `create_app(settings: Settings | None = None) -> FastAPI`. Jinja2 templates live in `web/templates/` and static CSS in `web/static/`. Autoescape stays on.
- **Lifespan:** if `ingest_enabled` is true, start a daemon thread running `ingest_loop(stop_event, settings)`, and stop it cleanly on shutdown.
- `web/ingest_loop.py`:
  - `run_ingest_once(settings, *, session_factory, client, now_ms) -> IngestStats`: logs the summary.
  - `ingest_loop(...)`: calls `run_ingest_once` every `poll_interval_min`. It must never die from an exception: log it and carry on.
  - On `RiotAuthError`, log an ERROR and send **one** alert to `alert_webhook_url` for each failure streak: "didyouhit: Riot API key rejected (HTTP 4xx), ingestion paused until it works again". Keep retrying on the normal interval. When a run succeeds again, clear the streak and send one "ingestion recovered" alert.
  - Alerts use `httpx`, never include the key or the webhook URL in logs, and alert failures are swallowed with a warning.

### 4. Routes
| Route | Content |
|---|---|
| `GET /` | This week: the week label, "Resets in Xd Yh" (computed server-side with `ms_until_reset`), and every board as a card. Group them into sections: **Big numbers** (peak_ap, peak_ad, peak_health, largest_crit), **Damage & utility** (damage_to_champions, damage_mitigated, ally_heal_shield, cc_time), **Per minute** (the 4 per-min boards), **This week's totals** (first_places, games_played). Each card shows the label and up to `display_limit` entries: position, Riot ID (links to the member page), the value, and the champion (single-game boards). If a board is empty, show "No games yet this week." |
| `GET /weeks` | Past weeks, newest first. For each week, a compact table of the winner (Riot ID, value, champion) for every board. Links to the week detail page. |
| `GET /weeks/{label}` | All boards for that week with limit 10, in the same layout as `/`. Return 404 for a bad label format, and 404 for a future week. A past week with no games shows the empty state. |
| `GET /members/{member_id}` | Riot ID, member since (date), then the Arena history, newest first, up to 50 games: date/time (in `week_tz`), champion, placement, augment IDs (plain numbers for now), damage to champions, peak AP, peak max health, biggest crit, CC time. Query `member_games` directly for this page (add a `web/queries.py` helper), since it needs more fields than `GameRow`. 404 for an unknown or inactive member. |
| `GET /join` | Form: Riot ID (`Name#TAG`), region select (the platform keys from `routing.PLATFORMS`, default `na1`, with friendly labels such as `na1 → North America`), invite code. If `invite_code` isn't configured, show "Sign-ups are closed right now." and no form. |
| `POST /join` | Wrong invite code → 403 and the form again with "That invite code isn't right." Then `register_member` → a 303 redirect to `/members/{id}?joined=1`, where that page shows "You're in! Your Arena games from the last 7 days will show up within ~15 minutes." Error messages: InvalidRiotId → "Enter your Riot ID like Name#TAG."; RiotIdNotFound → "We couldn't find that Riot ID in that region."; SignupUnavailable → "Sign-ups are temporarily unavailable. Try again later." Keep what the user typed on error, except the invite code. |
| `GET /healthz` | `{"ok": true}` |

Sign-up builds its own `RiotClient` from settings, and the app keeps one client per process. If `riot_api_key` is missing, joining raises SignupUnavailable.

### 5. Templates, style and formatting
- `base.html` has a header with the app name (links to `/`), and nav links (This week, Past weeks, Join).
- **Footer on every page**, verbatim from COMPLIANCE.md with `app_name` filled in: "{app_name} isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc."
- **Formatting filters:**
  - Integers get thousands separators (`115,190`).
  - Per-minute values: `dmg/min` and `HP/min` as integers; `s/min` with 1 decimal.
  - Seconds boards show `56s`.
  - Totals are integers.
  - Dates and times are shown in `week_tz`, e.g. `Sep 8, 9:14 PM`.
- **Style (`static/style.css`, hand-written, no frameworks, no JavaScript):**
  - Dark theme, with the big number as the visual hero of each card (large, bold, tabular numerals).
  - Cards in a responsive grid: 1 column at 375px wide, 2–4 on desktop. No horizontal scrolling at 375px.
  - Readable contrast (WCAG AA for body text).
  - Use CSS custom properties for colors.
  - A system font stack; no external fonts, images or CDNs.
  - No Riot logos or images.
- **Wording:** "board", "position", "winner". Never "rank", "ranked", "tier" or "MMR" anywhere in templates or output.

### 6. CLI
Add `didyouhit serve [--host 127.0.0.1] [--port 8000]` (uvicorn). The ingest loop follows `INGEST_ENABLED`.

### 7. Tests
Add `tests/test_web.py` and `tests/test_signup.py`, using FastAPI `TestClient` and the in-memory DB with seeded members and games. Add a fixture that seeds 2 members and games across the current week and last week, reusing the parsed 1750 fixture for one realistic row.
- `/`, `/weeks`, `/weeks/{label}`, `/members/{id}`, `/join` and `/healthz` return 200 with the seeded data. `/` shows `53,976` (thousands separator), and every section heading is present.
- **The footer string is present on every HTML route**, including the 404 and 403 pages.
- The rendered HTML of every route contains no `rank`, `tier` or `mmr` (case-insensitive, as whole words or prefixes).
- `/weeks/not-a-date` → 404, a future week → 404, unknown member → 404, inactive member → 404.
- The empty week shows the empty-state text.
- **Join:**
  - Invite code unset → closed message and no form.
  - Wrong code → 403 with the message.
  - Correct code with the respx-mocked account → 303 redirect, member created, and the member page shows the "You're in!" text.
  - A mocked 404 → the not-found message.
  - A mocked 401 → the unavailable message.
  - A bad format → the format message.
  - The API key never appears in any response body.
- **Ingest loop:**
  - `run_ingest_once` with mocks returns stats.
  - Auth-error streaks send exactly one alert for three consecutive failures, then one "recovered" alert (mock the webhook with respx).
  - The loop survives an arbitrary exception from one iteration.
  - `create_app` with `ingest_enabled=False` starts no thread.
- **XSS:** a member whose `game_name` is `<script>x</script>` renders escaped.

**Do not:**
- Add JavaScript, CSS frameworks, external fonts or images, or new dependencies beyond `python-multipart` (needed for form posts) without flagging them.
- Show champion images or augment names (T007).
- Modify `tests/fixtures/*`, `tools/`, `docs/`, `CLAUDE.md`, `DEEPSEEK.md`, or `data/didyouhit.db`.
- Run `git commit`.

## Acceptance criteria
1. `uv sync` succeeds. The only new dependency is `python-multipart`, if you needed it.
2. `uv run pytest -q` passes (all earlier tests plus everything above).
3. `uv run ruff check .` and `uv run ruff format --check .` are clean.
4. `uv run didyouhit serve --port 8765 &`, then `curl -s localhost:8765/` returns 200 and contains "isn't endorsed by Riot Games". `curl -s localhost:8765/weeks` shows the week `2026-09-07` from the real dev DB. Kill the server afterwards.
5. `grep -rniE "\brank|ranked|\btier|mmr" src/didyouhit` finds nothing.
6. `git status --short` shows no changes to forbidden paths.

## Report
Write `handoffs/reports/T004-report.md`, overwrite `handoffs/TO_CLAUDE.md`, set T004 to `review` in `BOARD.md`, run `python3 tools/notify.py --from deepseek --kind done "T004 finished: <one line>. Tell Claude: read handoffs/TO_CLAUDE.md"`, and tell the user. In the report, include the exact command the user should run to view the site locally.
