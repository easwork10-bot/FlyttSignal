# FlyttSignal developer entry point

Read only the documentation needed for the task:

- `docs/architecture.md`: boundaries and domain semantics.
- `docs/database.md`: persistence and migration rules.
- `docs/development.md`: setup, commands, activation and operations.
- `docs/sources/`: source-specific contracts and research.

## Map and commands

Backend: `backend/src/flyttsignal/{api,worker,ingestion,integrations,domains,db,scoring}`.
Frontend: `apps/web/src/{app,features,components,lib/api}`.
Tests and fixtures: `backend/tests`, `backend/fixtures`.

From backend: `uv sync --frozen`; `uv run pytest -q`; `uv run ruff check .`;
`uv run python scripts/export_openapi.py --check`.
From repo root: `pnpm --dir apps/web contracts:check`, `typecheck`, `lint`, `build`.
Docker: `docker compose up --build -d`; `docker compose logs --tail 50 api worker`.

## Boundaries

- Adapters own external protocols; ingestion orchestrates; domains are pure; repositories own SQL.
- Domains must not import API, DB, worker or integrations. Worker calls Python, not internal HTTP.
- API routes/mappers do not implement collection or query SQL. Frontend uses generated REST types.
- Use stable responsibility names; avoid version suffixes in filenames/functions and catch-all modules.
- Prefer the smallest correct change. Do not refactor unrelated working code.

## Invariants

Observation/event is not a signal or a confirmed move. Publisher is not provider.
Advertised availability is not an observed move date; never invent a +30-day move window.
Targetability is independent of signal inference. Unknown is not false or zero.
Current signal reads use `Signal.current()`; historical/as-of reads must preserve temporal validity.
Syndicated channels are not independent evidence. Context datasets cannot create synthetic signals.
Preserve source observations and real user data. Rebuild derived data where possible.
Before adding history/backup infrastructure ask what irreplaceable information would otherwise be lost.
No routine snapshots/backups, fixture fallback, silent live collection, or destructive DB reset.
Fresh DB: Alembic upgrade. Existing DB: never stamp without verified schema equivalence and authorization.
