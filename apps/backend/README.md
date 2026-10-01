# SupplyLens Backend

This is the FastAPI and SQLAlchemy backend for SupplyLens, managed with `uv`.

The current B0 foundation includes:

- `GET /health` for process liveness
- `GET /api/v1/health/ready` for PostgreSQL readiness
- lazy SQLAlchemy engine and session initialization
- Alembic configuration with an empty initial revision
- automated API/database unit tests and a Docker-backed migration test

The procurement, document-ingestion, and policy domains are not implemented yet.

## Setup

From the repository root, create the local environment file:

```powershell
Copy-Item .env.example .env
```

The development database uses:

```text
postgresql+psycopg://supplylens:localdev@127.0.0.1:5433/supplylens
```

Keep `.env` local and uncommitted. Never commit credentials or real supplier data.

Start PostgreSQL and install the locked dependencies:

```bash
docker compose up -d db
uv sync --project apps/backend --locked
```

Run the API:

```bash
make be
```

The health endpoints are available at:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/api/v1/health/ready`

Liveness returns `{"status":"ok"}` without database configuration. Readiness returns `{"status":"healthy"}` after a successful database check; missing configuration or an unavailable database returns `503` with a safe message.

## Quality and tests

Run these commands from the repository root:

```bash
make be-check
make be-lint
make be-test
make version-test
make be-test-integration
make docker-test-storage-stop
make docker-test-stop
```

`make be-test` runs unit/API tests and enforces the unit coverage configuration. It does not start Docker services. Running plain `uv run pytest` from `apps/backend` uses pytest's configured default test path, `src`, where the co-located unit tests live; integration tests under `tests/integration` are not included by default.

`make be-test-integration` runs tests marked `integration` from `tests/integration` and starts both disposable services: `db-test` on port `5434` and `minio-test` on port `9002`. The database test targets `supplylens_test` and verifies a clean Alembic upgrade and downgrade. Run both matching stop commands afterward. The development database and MinIO services are not used by these tests.

Useful migration commands are:

```bash
make db-current
make db-history
make db-upgrade
make db-check
```

## Project layout

```text
apps/backend/
|-- alembic/              # migration environment and revisions
|-- src/supplylens/       # application package
|-- tests/
|   |-- integration/      # explicit PostgreSQL and MinIO integration tests
|   `-- manual/           # VS Code REST Client checks
|-- alembic.ini
`-- pyproject.toml
```

## Development principles

- Keep AI optional and non-authoritative.
- Keep calculations deterministic and auditable.
- Preserve document provenance.
- Keep domain logic separate from provider-specific adapters.
- Validate against synthetic fixtures rather than live supplier data.

## Related documentation

- [Main project README](../../README.md)
- [Architecture document](../../docs/SupplyLens-Architecture-v0.1.md)
- [MVP definition](../../docs/SupplyLens-MVP-Definition-v0.1.md)
- [Repository guidance](../../AGENTS.md)
