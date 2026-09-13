# Development and operations

## Setup

Docker Desktop with Linux containers is sufficient to run the app. From the repository root:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps -a
```

Before startup, set private POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB values. Keep DATABASE_URL consistent for local Python access. Compose constructs its internal URL from these values. Never commit .env or put secrets in NEXT_PUBLIC_* variables.

Default web/API endpoints are localhost:3000 and localhost:8000/api. Check POSTGRES_PORT in configuration instead of assuming a host DB port; containers use postgres:5432. Changing the browser API port requires rebuilding web with NEXT_PUBLIC_API_BASE_URL. The current CORS policy permits http://localhost:3000; changing the web origin also requires an intentional API configuration change.

Startup order: healthy PostgreSQL → successful one-shot migrate → API/worker → web. A completed migrate container exiting 0 is normal. A fresh database has reference rows but no collected listings or active pilot model. Pilot 409 (incomplete dimension scope) is expected until activation.

## Local tools and checks

Use Python 3.12, uv and Node 22 with the packageManager pinned in apps/web/package.json.

```powershell
cd backend
uv sync --frozen
uv run pytest -q
uv run ruff check .
uv run python scripts/export_openapi.py --check
cd ..
pnpm --dir apps/web install --frozen-lockfile
pnpm --dir apps/web contracts:check
pnpm --dir apps/web typecheck
pnpm --dir apps/web lint
pnpm --dir apps/web build
```

If using the existing root Windows venv, `./.venv/Scripts/python.exe` can run `-m pytest backend -q`, `-m ruff check backend` and `backend/scripts/export_openapi.py --check` from the repo root. Do not assume that a root venv exists on a fresh checkout; uv setup above creates backend/.venv.

When schemas intentionally change, run export_openapi.py without --check, then `pnpm --dir apps/web contracts:generate`. Do not hand-edit generated.ts or duplicate its shapes. CI checks backend tests/Ruff/OpenAPI and frontend contracts/typecheck/lint/build. Unit tests use mocks or isolated fixtures where appropriate; a green unit suite is not proof of live source semantics or PostgreSQL startup.

For schema changes also initialize an empty isolated PostGIS database, apply only the current migrations, verify seed identities and API/worker startup. Never aim these checks at the existing local database.

## Docker commands

```powershell
docker compose logs --tail 100 api worker web
docker compose run --rm --no-deps migrate
docker compose exec api alembic current
docker compose exec api alembic heads
docker compose build api worker migrate web
docker compose up -d
docker compose down
```

The dedicated Compose project, network and database volume are named for FlyttSignal. Avoid broad Docker prune commands. Use `docker context show` and `docker compose ps -a` if Docker Desktop looks empty. A full repo bind mount over /app can hide the image's installed venv; use the built image or mount only the needed source path.

## Collection and lifecycle

All live collection is deliberate. Runtime gates include UPPSALA_BOSTADSFORMEDLING_LIVE_ENABLED, HOMEQ_PUBLIC_LIVE_ENABLED, HSB_PUBLIC_LIVE_ENABLED, HEIMSTADEN_LIVE_ENABLED, SCB_LIVE_ENABLED, LANTMATERIET_LIVE_ENABLED and UPPSALA_OPEN_DATA_LIVE_ENABLED. Read [source reviews](sources/reviews/README.md) and .env.example for endpoints, caps, timeouts and credentials.

Change the required environment flag, then recreate only the worker:
`docker compose up -d --no-deps --force-recreate worker`.
Startup reconciles configured source enablement. To stop collection immediately, stop the worker; changing .env alone does not change an existing process.
Fixtures never become an automatic fallback when a source is disabled or unavailable.

Use existing verify_ubf_live.py/verify_rental_live.py commands with --help for bounded source diagnostics, and ingest_rental_live.py for explicitly requested writes. Context fixture verifiers may write to their target database: use isolated test data, not an unreviewed live invocation.

Source execution success is independent of completeness. Inspect `/api/source-runs` and `/api/sources/{source_key}/lifecycle-readiness`. READY requires evidence-backed scheduled runs under one rule. It does not activate removals by itself.
UBF lifecycle has a separate enable flag and grace-run setting. Incomplete/manual/capped/failed inventories cannot authorize missing-item removal. Heimstaden's bounded public search is incomplete scope even when zero results are valid.

SCB is aggregate context. Uppsala Open Data is geometry context. Lantmäteriet requires provisioned access and OAuth configuration; only the implemented exact-address/register-unit contract is admitted. Keep credentials server-side and attribution intact.

## Evaluation and pilot activation

The existing commands separate preview from --apply:

```powershell
docker compose run --rm --no-deps api python scripts/materialize_score_run.py
docker compose run --rm --no-deps api python scripts/materialize_score_run.py --apply
docker compose run --rm --no-deps api python scripts/activate_score_run.py --run-id <reviewed-run-id>
docker compose run --rm --no-deps api python scripts/activate_score_run.py --run-id <reviewed-run-id> --reason "<decision>" --apply
```

Only materialize a run when evaluating/serving a chosen model; do not schedule routine captures just to accumulate history. The activation must contain all three dimensions for one shared population. Replacing an activation uses --replace-run-id with the expected current run. Review before applying. The scope is internal-pilot, not global commercial authorization.

Use `/api/score-runs`, `/api/score-activations/internal-pilot?city_id=1` and signal details to inspect provenance. New signals need membership in a complete activated run before product prioritization. Never seed invented data/ratings to make the pilot look ready.

For a real pilot, agree a service area and test period, assign a pseudonymous code, and use `/pilot?pilot=<code>`. The code is not authentication. Without a code the page is internal preview without shown/opened tracking. Keep the company mapping outside the application. Activity records unique SHOWN/OPENED; REVIEWED derives from feedback. Ratings are USEFUL/MAYBE/NOT_USEFUL with a controlled reason.

Do not change the cohort or activated run during an agreed pilot without coordination. Inspect useful-rate with its denominator, rejection reasons, preferred timing/geography and qualitative feedback. AI-assisted review is not independent ground truth.

## Maintenance and troubleshooting

Existing classification, measurement and outcome backfills default to preview. Use --help and inspect scope before --apply. Missing measurement inputs remain explicit, not zero. Do not reconstruct historical outcomes from mutable current values.
Validation commands create/export/import reviewed samples; import retains verdict provenance and must not silently overwrite user judgments.
load_demo_data.py is explicit demo tooling only; cleanup_fixture_data.py can delete data and needs reviewed scope.

A tile outage should not block tables or source/evidence views. A missing activation is different from missing listings. Failed migrations require logs/diagnosis, not volume deletion. Routine changes do not need new backups/manifests/snapshots.

Historical backup/source captures have been moved to a local archive outside the repository. They are not needed for installation. Held review data may contain unique judgments or historical observations; do not delete it or add it to a fresh public history without checking content and reconstructability.
