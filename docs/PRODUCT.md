# Product

**Name:** didyouhit.gg (package `didyouhit`, `APP_NAME` setting). The name and domain must never contain Riot trademarks (League, LoL, ARAM, Arena, Mayhem, Riot, champion names).

## Pitch
Arena is about hitting absurd numbers. Every week, see who in your group hit the biggest ones.

## Background
Originally planned for ARAM: Mayhem. Phase 1 (2026-09-27) showed Mayhem matches are absent from the public Riot API entirely (not even listed), so we pivoted to **Arena**, which returns full match + timeline data. Mayhem can be added later if Riot opens it (queue 2400).

## Users & rollout
1. **MVP (now):** the owner's friend group. Invite-code sign-up with a Riot ID. Runs on a personal API key (allowed for "a small private community").
2. **Public:** after traction. Production key, own domain, ToS + Privacy pages, then Riot Sign On (RSO) replaces typed Riot IDs.
3. **Later:** Discord bot posting weekly winners (primary growth channel); Mayhem if the API allows.

## Weekly challenges (MVP)
The week runs Monday 00:00 → next Monday 00:00 in `WEEK_TZ` (default `America/Los_Angeles`). A game belongs to the week containing its **end** time.

**Best single game** boards (value from one game; top N members; one entry per member, their best):
| key | label | source |
|---|---|---|
| `peak_ap` | Highest AP | timeline peak `abilityPower` |
| `peak_ad` | Highest AD | timeline peak `attackDamage` |
| `peak_health` | Most max health | timeline peak `healthMax` |
| `largest_crit` | Biggest crit | `largestCriticalStrike` |
| `damage_to_champions` | Most damage | `totalDamageDealtToChampions` |
| `damage_mitigated` | Most damage mitigated | `damageSelfMitigated` |
| `ally_heal_shield` | Most healing + shielding on allies | `totalHealsOnTeammates + totalDamageShieldedOnTeammates` |
| `cc_time` | Most CC time | `timeCCingOthers` |

Per-minute variants (`*_per_min`) for `damage_to_champions`, `damage_mitigated`, `ally_heal_shield` and `cc_time`, so long games don't dominate. Peak stats and crit get no per-minute variant.

**Weekly totals:** `first_places` (count of 1st-place finishes), `games_played`.

Ties: the earlier game wins.

## Pages (MVP)
- **This week:** all boards, top 5 each, plus a countdown to reset.
- **Past weeks:** list of weeks with each board's winner; week detail page.
- **Member page:** their Arena history (champion, placement, augments picked, key stats), newest first.
- **Join:** Riot ID + region + invite code.
- The footer on every page carries Riot's legal boilerplate.

## Explicit non-goals
Skill rating, "ranked" anything, augment/item win rates, tier lists, client-side data, and non-member profiles.
