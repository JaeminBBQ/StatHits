# Architecture

## Stack
| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.12 (managed by `uv`) | Phase 1 probe is Python; simple; DeepSeek-friendly |
| Web | FastAPI + Jinja2 server-rendered templates, plain CSS | No JS build step; pages are mostly tables |
| DB | SQLite (WAL mode) via SQLAlchemy 2.0 ORM, Alembic migrations | One file, zero cost; swap to Postgres via URL if ever needed |
| HTTP client | `httpx` (sync) | Simple, easy to mock with `respx` |
| Config | `pydantic-settings` reading `.env` | |
| Scheduling | Ingestion loop in a background thread inside the web process (single instance), plus a CLI for manual runs | No separate worker to pay for |
| Tests / lint | `pytest`, `respx`, `ruff` | |
| Deploy | Single small container (Fly.io / cheap VPS; decided later) with a volume for SQLite | ~$0–6/mo |

## Layout
```
src/didyouhit/
  config.py          # Settings (APP_NAME, RIOT_API_KEY, DATABASE_URL, WEEK_TZ, INVITE_CODE, ...)
  db.py              # engine/session setup
  models.py          # ORM models
  riot/
    client.py        # rate-limited Riot API client (T002)
    routing.py       # platform -> regional routes
  parsing.py         # pure: match+timeline JSON -> records (T001)
  ingest.py          # ingestion service (T002)
  weeks.py           # week window math (T003)
  boards.py          # board definitions + queries (T003)
  web/               # FastAPI app, routes, templates, static (T004)
  cli.py             # `didyouhit` CLI: add-member, ingest, ...
migrations/          # Alembic
tests/               # pytest; tests/fixtures holds anonymized real API JSON
tools/phase1_probe.py
```

## Data model
Only registered members' data is stored. No raw match JSON, no non-member names/PUUIDs.

**members**: `id` PK, `puuid` (unique), `game_name`, `tag_line`, `platform` (e.g. `na1`), `created_at_ms`, `active` bool, `last_polled_at_ms` nullable, `backfill_from_ms` (start of the week they joined).

**matches**: the "seen" set, which prevents re-fetching. `match_id` PK (e.g. `NA1_5638612201`), `platform`, `queue_id`, `game_mode`, `game_start_ms`, `game_end_ms`, `duration_s`, `is_arena` bool, `is_valid` bool (false for remakes/too short), `fetched_at_ms`. Non-Arena matches get a row too (with `is_arena=false`) so they're never fetched again.

**member_games**: one row per (member, Arena match). Unique `(match_id, member_id)`.
- identity: `champion_name`, `champion_id`, `placement`, `subteam_id`
- augments: `augments` (JSON list of non-zero `playerAugment1..6` IDs, in order)
- match stats: `damage_to_champions`, `physical_damage_to_champions`, `magic_damage_to_champions`, `true_damage_to_champions`, `largest_crit`, `damage_taken`, `damage_mitigated`, `total_heal`, `heals_on_teammates`, `shields_on_teammates`, `cc_time`, `largest_multikill`, `penta_kills`, `gold_earned`, `damage_per_minute` (from `challenges`, nullable)
- timeline stats: `final_ap`, `peak_ap`, `final_ad`, `peak_ad`, `final_health_max`, `peak_health_max`, `final_armor`, `final_mr`, `final_attack_speed`, `peak_attack_speed` (nullable if no timeline)
- denormalized for fast weekly queries: `game_end_ms`, `duration_s`

Per-minute values are computed at query time (`value / (duration_s / 60)`).

## Arena data facts (verified against real data, 2026-09-27)
- Identify Arena by `info.gameMode == "CHERRY"`. Queue IDs seen: 1700, 1740, 1750. Riot's `queues.json` lacks 1740/1750, so don't rely on a queue whitelist.
- The current format has **18 participants, 6 subteams of 3** (`playerSubteamId`, `subteamPlacement`/`placement` 1–6). Never hardcode team or participant counts.
- Timeline `participantFrames` are keyed by `participantId` as strings (`"1"`…`"18"`); map PUUID → participantId via `info.participants`.
- Timeline frames are ~60s snapshots. "Peak" = max across frames (short buffs between frames are missed; accepted).
- `playerAugment5/6` are `0` when unused.
- `challenges` may be missing in some matches; treat it as optional.

## Ingestion design (T002)
Every `POLL_INTERVAL_MIN` (default 15), for each active member:
1. `GET match-v5 /by-puuid/{puuid}/ids?startTime={s}&count=100` (paginate), where `s` = max(`backfill_from_ms`, last poll − 1h overlap), in seconds. Use no queue filter, so new Arena queue IDs are picked up automatically.
2. For each ID not in `matches`: fetch the match and insert a `matches` row. If it's Arena and valid, fetch the timeline and create `member_games` for **every active member** in that match (one fetch serves the whole group).
3. If an ID is in `matches` and is valid Arena, but this member has no `member_games` row (they joined after the match was ingested for someone else), re-fetch that match and timeline once to fill it in.
- Validity: `is_valid = not any(p.gameEndedInEarlySurrender) and duration_s >= MIN_GAME_DURATION_S` (default 300).
- Rate limiting: respect `Retry-After` on 429s; stay under the configured app limits (dev/personal key: 20/1s, 100/120s); retry 5xx and network errors with backoff.
- Routing: `account-v1` supports americas/asia/europe only; `match-v5` supports americas/europe/asia/sea. The map lives in `riot/routing.py` (copy from `tools/phase1_probe.py`).

## Auth
MVP: invite code + typed Riot ID → `account-v1` lookup → member. Keep sign-up behind a small interface (`signup.py`) so RSO can replace it later without touching ingestion or boards.
