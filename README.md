<div align="center">

# SupplyLens

### From supplier PDFs to trustworthy purchase intelligence

**Reviewable extraction · Human validation · Deterministic calculations · Evidence-first workflows**

![Version](https://img.shields.io/badge/version-v0.7.0-8b5cf6)
![Status](https://img.shields.io/badge/status-early%20scaffold-orange)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688)
![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20TypeScript-149eca)
![Database](https://img.shields.io/badge/database-PostgreSQL%20%2B%20pgvector-4169e1)
![AI](https://img.shields.io/badge/AI-optional-8b5cf6)

</div>

---

## 🚀 Product vision

SupplyLens turns supplier PDFs into structured, reviewable purchase data for small retailers without letting AI blur the lines between evidence, confirmed records, and business policy.

> The document is evidence. The approved record is truth. The model is an assistant, not an authority.

This repository is intentionally still in the early scaffold phase, but the architecture and guardrails are already clear:

- no-LLM path is the real product baseline
- human confirmation remains the source of truth
- calculations must be deterministic and auditable
- provenance and versioning matter more than convenience

---

## 🧭 Where the project stands today

| Area | Current state | Realistic status |
| --- | --- | --- |
| Backend | FastAPI app with `/health` and `/api/v1/health/ready` | Health checks and database wiring are live; domain workflow is still planned |
| Frontend | Vite + React + TypeScript starter | A working UI shell exists, but not the business workflow yet |
| Database | PostgreSQL 17 + pgvector via Docker Compose | Ready for local development and future migrations |
| AI | Optional integration layer only | Not required for the MVP path |
| Tests | Unit/API tests by default; PostgreSQL and MinIO integration tests run explicitly | `pytest` and `make be-test` run unit tests; `make be-test-integration` runs integration tests |

### ✅ What is implemented

- FastAPI application entry point with `/health`
- v1 router mounted at `/api/v1`
- readiness endpoint that checks PostgreSQL connectivity
- SQLAlchemy session factory and lazy engine startup
- Alembic scaffold for future schema evolution
- Docker Compose database services for local development and isolated migration tests
- FastAPI liveness/readiness and database unit tests with a 100% coverage gate
- root `Makefile` with backend/frontend/bootstrap and quality helpers

### ⏳ What is still planned

- digital PDF ingestion and extraction
- reviewed purchase record models
- catalog matching and policy layer
- report generation and search
- worker orchestration and provenance tracking
- end-to-end product test suite and validation flows

---

## 🏗️ Architecture at a glance

```mermaid
flowchart LR
    UI[React + TypeScript UI] --> API[FastAPI API]
    API --> DB[(PostgreSQL + pgvector)]
    API --> STORE[(Private PDF storage)]
    WORKER[Python worker] --> DB
    WORKER --> STORE
    WORKER --> EXTRACT[Digital PDF extraction tools]
    API -. optional .-> LLM[LLM adapter]
```

The app is organized as a modular backend with API and worker entry points, not a microservice fleet. The real product logic stays deterministic and provider-agnostic behind adapters.

---

## 🛡️ Guardrails and operating principles

- Full purchase workflow must work with no LLM credentials.
- Extracted values remain suggestions until a human confirms them.
- Money and quantities use explicit deterministic logic.
- Documents keep provenance at source-page and source-record level.
- LLM output can support retrieval or drafting, but it never becomes the authority.
- Real supplier PDFs and private business data stay out of public fixtures or logs.

---

## 📁 Repository map

```text
SupplyLens/
├── AGENTS.md              # repository rules and contributor guidance
├── Makefile               # primary local workflow commands
├── compose.yaml            # PostgreSQL 17 + pgvector local stack
├── apps/
│   ├── backend/           # FastAPI app and database/migration setup
│   └── web/               # React + TypeScript + Vite app
├── docs/                  # product and technical design docs
├── fixtures/              # synthetic PDFs and expected JSON
├── infra/                 # deployment placeholder
├── specifications/        # engineering process and PR guidance
│   └── pull-request-definition.md
└── README.md              # this overview
```

---

## ⚙️ Local setup

### Prerequisites

- Python 3.14
- [uv](https://docs.astral.sh/uv/)
- Node.js + npm
- Docker + Docker Compose

### One-time environment setup

```powershell
# from the repo root
Copy-Item .env.example .env
```

The default local backend env points to:

```text
postgresql+psycopg://supplylens:localdev@127.0.0.1:5433/supplylens
```

This matches the local database in `compose.yaml`.

### Use the Makefile

```bash
make setup
make hooks
make be
make fe
make check
make docker-start
make be-test-integration
make docker-test-storage-stop
make docker-test-stop
```

### Quality gates

Run checks locally before pushing instead of before every commit:

```bash
pre-commit install --hook-type pre-push
```

This installs the repository hooks for the `pre-push` stage, so the checks fail before a push is accepted. You can still run them manually at any time with:

```bash
pre-commit run --all-files
```

### Direct commands

```bash
# database
cd /path/to/SupplyLens
docker compose up -d db

# backend
cd apps/backend
uv sync --locked
uv run uvicorn supplylens.api:app --reload

# frontend
cd apps/web
npm ci
npm run dev
```

### Useful validation checks

```bash
# backend syntax, Ruff, and unit/API tests (no Docker services)
make be-check
make be-lint
make be-test

# PostgreSQL and MinIO integration tests (Docker services)
make be-test-integration
make docker-test-storage-stop
make docker-test-stop

# version automation
make version-test

# frontend lint/build
make fe-lint
make fe-build

# database migration checks
make db-check
make db-upgrade
```

From `apps/backend`, plain `uv run pytest` uses the configured default test path
and runs the co-located unit tests. Integration tests are outside that default
path and run only through `make be-test-integration`.

---

## 🧪 Current workflow and checks

The repo is deliberately lightweight, but the working flow is clear:

1. install the locked backend and frontend dependencies with `make setup`
2. start PostgreSQL via Docker and apply/check migrations
3. start the backend and verify both health endpoints
4. run `make check` for backend and frontend quality gates
5. run `make be-test-integration`, then remove the disposable test services with `make docker-test-storage-stop` and `make docker-test-stop`
6. keep feature work grounded in synthetic documents, not real supplier data

### Health endpoints

- `GET /health` → service liveness
- `GET /api/v1/health/ready` → checks database connectivity and returns `503` if unavailable

---

## 📚 Read the project docs

- [Backend setup guide](apps/backend/README.md)
- [Frontend setup guide](apps/web/README.md)
- [Architecture deep dive](docs/SupplyLens-Architecture-v0.1.md)
- [MVP definition](docs/SupplyLens-MVP-Definition-v0.1.md)
- [Contributing rules](AGENTS.md)

---

## 🧠 Agent and workflow guidance

The project intentionally keeps AI support secondary to deterministic business logic. Contributor guidance lives in [AGENTS.md](AGENTS.md), and the repo is designed so that coding standards, guardrails, and validation remain explicit rather than hidden inside tooling.

This keeps the engineering workflow aligned with the product mission:

- AI augments, it does not decide
- provenance is required
- human review stays central
- the data model remains deterministic and explainable

---

## 🗺️ Roadmap

```mermaid
flowchart LR
    A[Scaffold] --> B[Upload + review]
    B --> C[Extraction + reconciliation]
    C --> D[Catalog + policy engine]
    D --> E[Reports + analytics]
    E --> F[Search + optional AI]
    F --> G[Production readiness]
```

Each phase is expected to work end to end using synthetic fixtures before the project expands further.

---

## 🤝 Contributing

Start with the relevant feature slice, keep the work grounded in synthetic examples, preserve provenance, and do not introduce hidden business assumptions. For the exact repo conventions and branch/PR expectations, follow [AGENTS.md](AGENTS.md).
