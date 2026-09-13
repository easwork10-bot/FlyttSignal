# FlyttSignal / FlyttRadar

FlyttSignal collects housing observations and turns them into traceable indicators of possible housing changes. FlyttRadar is its internal web interface. Signal Strength, Data Confidence and Timing are separate rule-based dimensions—not probabilities of household moves.

## Run

Install Docker Desktop with Linux containers. From the repository root:

```powershell
Copy-Item .env.example .env
# Set private database credentials in .env before starting.
docker compose up --build -d
docker compose ps -a
```

Open [FlyttRadar](http://localhost:3000) or [API documentation](http://localhost:8000/docs).
Collection is opt-in. A fresh database has reference data, not live listings or an activated score model. The pilot API returns 409 until a complete dimension run is deliberately activated.

## Repository

- `backend/src/flyttsignal/`: FastAPI, worker, source integrations, domains and persistence.
- `backend/migrations/`: canonical Alembic baseline and subsequent schema changes.
- `backend/tests/`, `backend/fixtures/`: regression tests and isolated source samples.
- `apps/web/`: Next.js/TypeScript UI and generated OpenAPI client.
- `.github/workflows/ci.yml`: backend, contract and frontend checks.

## Documentation

- [Architecture and domain semantics](docs/architecture.md)
- [Database and reconstructability](docs/database.md)
- [Development, testing and operations](docs/development.md)
- [Source registry](docs/sources/registry/README.md)
- [Source reviews](docs/sources/reviews/README.md)
- [Source access policy](docs/sources/access-policy.md)
- [AI/developer entry point](AGENTS.md)

This is an internal application without production authentication or billing. Do not expose it publicly without a separate deployment/security review. The pilot code is not authentication.
