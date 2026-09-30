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
Copy-Item apps/backend/.env.example apps/backend/.env
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
make docker-test-stop
```

`make be-test` runs tests that do not need PostgreSQL and enforces the unit coverage configuration. `make be-test-integration` starts only the disposable `db-test` Compose service on port `5434`, targets the `supplylens_test` database, and verifies a clean Alembic upgrade and downgrade. Run `make docker-test-stop` afterward. The development database on port `5433` is not used by the integration test.

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
|   |-- unit/             # automated API and database tests
|   |-- integration/      # isolated PostgreSQL migration test
|   `-- manual/           # VS Code REST Client checks
|-- .env.example
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
