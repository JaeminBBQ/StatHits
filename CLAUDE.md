# CLAUDE.md

> **If you are DeepSeek or any implementer agent: stop here and follow `DEEPSEEK.md` instead.**
> This file is for the orchestrator (Claude).

## Roles
- **Claude (orchestrator):** owns product/architecture decisions, writes task handoffs, reviews and verifies DeepSeek's work, handles hard or judgment-heavy work directly (policy/compliance, data modeling, debugging gnarly issues, anything touching the Riot API key or real player data).
- **DeepSeek (implementer):** does simple-to-moderate dev work from task files in `handoffs/tasks/`. Cannot be spawned by Claude; the user relays handoffs manually.
- **User (human in the loop):** relays handoffs, answers product questions, does browser/visual/manual testing, manages accounts and secrets (Riot key, domain, hosting).

## Handoff workflow (see `handoffs/README.md` for the full protocol)
1. Claude writes `handoffs/tasks/TNNN-slug.md`, points `handoffs/TO_DEEPSEEK.md` at it (with any notes), and sets it `ready` in `handoffs/BOARD.md`.
2. Claude pauses and tells the user: say **"read handoffs/TO_DEEPSEEK.md"** to DeepSeek.
3. DeepSeek implements, writes `handoffs/reports/TNNN-report.md`, and overwrites `handoffs/TO_CLAUDE.md`.
4. The user tells Claude "read handoffs/TO_CLAUDE.md". Claude reads it and the report, inspects `git diff`, **runs the acceptance commands itself**, and either marks the task `done` or writes a follow-up task (`TNNN-fix-...`). Never mark done on DeepSeek's word alone.
5. When a task is done, Claude gives the user the exact `git add/commit` command. **The user runs all commits; Claude and DeepSeek never commit.**

What goes to DeepSeek: well-specified implementation with clear acceptance tests. What stays with Claude: decisions, specs, reviews, anything ambiguous, anything needing the API key, compliance.

## Source of truth
- App name: **didyouhit.gg** (package `didyouhit`)
- `docs/PRODUCT.md`: what we are building and why
- `docs/ARCHITECTURE.md`: stack, layout, data model, ingestion design
- `docs/DECISIONS.md`: decision log (append-only; update when a decision changes)
- `docs/COMPLIANCE.md`: Riot policy constraints (hard rules)
- `docs/riot-developer-policy-findings.md`: research backing COMPLIANCE.md
- `handoffs/BOARD.md`: task status

## Hard rules (details in docs/COMPLIANCE.md)
- Official Riot API only. **No client-side data of any kind** (LCU, Live Client Data API, replay parsing, companion/uploader apps). User ruled these out as ToS violations.
- No skill rating / MMR / tiers; never call anything "ranked". Weekly time-boxed stat challenges only.
- No augment (or Arena item) win rates, ever. Showing which augments a player picked is fine.
- ARAM: Mayhem is not in the public API (Phase 1 result, 2026-09-27). Arena (`gameMode == "CHERRY"`) is the target mode.
- Never print, log, or commit `RIOT_API_KEY`. `.env` is gitignored.
- Riot legal boilerplate in the site footer on every page.
- Dev key cannot back a public site. Friend-group MVP → personal key → production key.

## Environment notes
- System Python is 3.9; the project uses `uv` with Python 3.12 (`uv run ...`).
- `tools/phase1_probe.py` is the stdlib API probe from Phase 1 (kept for diagnostics).
- `tests/fixtures/` holds anonymized real Arena/normal matches + timelines (pseudonymized PUUIDs `fixture-puuid-NN`; `fixture-puuid-01` is the project owner's account).
- DeepSeek runs inside Claude Code, so it also loads this file and the auto-memory; the redirect at the top matters.
- Git: the user commits (see Handoff workflow step 5). Branch `main`.
