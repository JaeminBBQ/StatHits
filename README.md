# didyouhit.gg

Weekly Arena stat challenges for a friend group, computed from official Riot
API data. See `docs/PRODUCT.md` for what we're building and why.

## Dev commands

Python 3.12 via `uv` (system Python is 3.9; don't use it):

```sh
uv sync                    # create the venv and install deps + this package
uv run pytest -q           # tests (offline, against tests/fixtures/)
uv run ruff check .        # lint
uv run ruff format --check .  # format check
uv run alembic upgrade head   # create/migrate the SQLite database
uv run didyouhit parse-fixture <match.json> <timeline.json> <puuid>  # debug aid
```

## Repo guide

- `CLAUDE.md` — orchestrator guide. `DEEPSEEK.md` — implementer guide.
- `docs/` — product, architecture, decisions, compliance.
- `handoffs/` — task board and handoff protocol between the two.
- `tests/fixtures/` — anonymized real API responses; tests never hit the network.
