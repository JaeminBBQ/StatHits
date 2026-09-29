# Task Board

| ID | Task | Owner | Status | Depends on |
|---|---|---|---|---|
| T001 | Scaffold, config, DB models + migration, pure parsing of match/timeline → records | DeepSeek | done | — |
| T002 | Riot API client (rate limits, retries, routing) + ingestion service + CLI (`add-member`, `ingest`) | DeepSeek | done | T001 |
| T002a | Fix: poll cursor must not skip failed matches; a match-level 403 must not abort ingestion | DeepSeek | done | T002 |
| T003 | Week windows + board definitions/queries + past-week winners | DeepSeek | done | T001, T002a |
| T004 | Web UI: this week, past weeks, member page, join page, footer; background ingest loop | DeepSeek | ready | T002, T003 |
| T005 | First live run with a real key; data sanity check against the user's games | Claude + user | done | T002 |
| T006 | Visual/browser review of the UI | User | planned | T004 |
| T007 | Augment names/icons (Data Dragon / game data) on member pages | DeepSeek | planned | T004 |
| T008 | Deploy (host choice, volume, secrets) for the friend-group MVP | Claude + user | planned | T004 |
| T009 | Discord bot: weekly winners post | — | planned | T008 |

Only `ready` tasks have full specs in `tasks/`. Claude writes the next spec after reviewing the previous task, so later specs can take what was learned into account.
