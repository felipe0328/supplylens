# SupplyLens Backend

<div align="center">

![Backend](https://img.shields.io/badge/backend-FastAPI-009688)
![Python](https://img.shields.io/badge/python-3.14-3776AB)
![Database](https://img.shields.io/badge/postgres-17-336791)
![Status](https://img.shields.io/badge/status-early%20scaffold-orange)

</div>

---

## 🧩 What this service is

This is the backend for SupplyLens, built with FastAPI and SQLAlchemy, and managed with `uv`.

At the moment, the backend is intentionally a thin scaffold:

- FastAPI app boots successfully
- `/health` returns liveness status
- `/api/v1/health/ready` verifies database connectivity
- SQLAlchemy engine/session setup is in place
- Alembic scaffolding is ready for future schema work

The real procurement, document ingestion, and policy logic is still to be built.

---

## 📍 Current implementation snapshot

```text
apps/backend/
├── alembic/              # migration configuration and revision history
├── src/supplylens/
│   ├── api.py            # FastAPI app bootstrap
│   ├── database/
│   │   └── database.py  # DB URL, engine, session setup, health check
│   ├── routes/
│   │   └── v1/routes.py # readiness route
│   ├── models/          # package placeholder for future domain models
│   └── ...
├── tests/
│   └── manual/          # VS Code REST Client health checks
├── .env.example         # template for local DB env
├── pyproject.toml       # Python project config and tooling
├── alembic.ini          # migration config
└── README.md            # this guide
```

---

## ⚙️ Setup

### 1) Create the local env file

From the repository root:

```powershell
Copy-Item apps/backend/.env.example apps/backend/.env
```

The default local value is:

```text
DATABASE_URL=postgresql+psycopg://supplylens:localdev@127.0.0.1:5433/supplylens
```

> Keep this file local and uncommitted. Never commit credentials or real supplier data.

### 2) Start PostgreSQL

```bash
docker compose up -d db
```

This starts the local PostgreSQL 17 + pgvector service defined in the project root `compose.yaml`.

### 3) Install backend dependencies

```bash
cd apps/backend
uv sync
```

### 4) Run the API

```bash
cd apps/backend
uv run uvicorn supplylens.api:app --reload
```

The app will be available at:

- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/api/v1/health/ready

---

## ✅ Health checks

### Liveness

```bash
curl http://127.0.0.1:8000/health
```

Expected result:

```json
{"status": "ok"}
```

### Readiness

```bash
curl http://127.0.0.1:8000/api/v1/health/ready
```

Expected result:

```json
{"status": "healthy"}
```

If the database is not configured or is unreachable, the endpoint returns `503` with an error detail.

---

## 🛠️ Useful commands

From the repo root, use the project `Makefile`:

```bash
make setup
make be
make be-check
make db-check
make db-upgrade
make docker-start
```

Direct backend commands:

```bash
cd apps/backend
uv sync
uv run python -m compileall -q src
uv run alembic current
uv run alembic history
uv run alembic check
```

---

## 🧪 Testing and quality

The backend is still in the scaffold stage, so the most important checks at the moment are:

- Python syntax compilation
- database connectivity checks
- migration sanity checks
- manual API health validation

The repo conventions call for backend tests in `apps/backend/tests/` using `pytest` and names like `test_*.py` or `*_test.py`.

---

## 📌 Development principles

The backend follows the same product rules as the rest of the repo:

- keep AI optional and non-authoritative
- remain deterministic and auditable
- preserve document provenance
- keep domain logic separate from provider-specific adapters
- validate against synthetic fixtures rather than live supplier data

---

## 🔗 Related docs

- [Main project README](../../README.md)
- [Frontend README](../../apps/web/README.md)
- [AGENTS guide](../../AGENTS.md)
- [Architecture document](../../docs/SupplyLens-Architecture-v0.1.md)
