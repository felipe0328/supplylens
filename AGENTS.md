# Repository Guidelines

## Agent Authorization and Git Boundaries

- Default to read-only work. If the developer asks for a review, explanation, diagnosis, opinion, or ideas, inspect the repository and report findings without modifying files.
- Modify files only when the developer explicitly asks for an implementation or names a file or artifact to update. Keep changes within that request; propose unrelated improvements instead of applying them.
- An explicit edit request authorizes only the edits needed for that request. It does not authorize staging, committing, pushing, opening a pull request, or changing unrelated work.
- Never stage AI-authored or AI-modified files unless the developer explicitly asks for those exact changes to be staged. Preserve the existing Git index and do not disturb developer-staged work.
- Before editing, inspect `git status` and relevant diffs. Treat all existing changes as developer-owned and preserve them.
- Ask before destructive or difficult-to-reverse operations and before any action whose scope is ambiguous.

## Project Purpose and Sources of Truth

SupplyLens turns supplier purchase PDFs into reviewable, traceable purchase and product data for small retailers. The core workflow must work without an LLM; AI assistance is optional and must never replace validation, human confirmation, or deterministic calculations.

- `docs/SupplyLens-MVP-Definition-v0.1.md` is the product-scope source of truth.
- `docs/SupplyLens-Architecture-v0.1.md` is the technical design reference and intended modular direction.
- `specifications/` contains reusable engineering-process definitions. Follow `specifications/pull-request-definition.md` for pull requests.
- Keep real supplier data, credentials, customer information, and private pricing policies out of the repository.

## Current Implementation Snapshot

The repository is still an early scaffold; the architecture document describes intended boundaries, not functionality that already exists.

- `apps/backend/` is a Python 3.14 FastAPI package managed with `uv`. `supplylens.api` exposes a process liveness route at `GET /health` and mounts the v1 router at `/api/v1`.
- `GET /api/v1/health/ready` checks PostgreSQL connectivity through the database session module and returns `503` when configuration or connectivity fails.
- `supplylens.database.database` loads `DATABASE_URL` from the environment, creates the SQLAlchemy engine and session factory lazily, yields sessions, and runs the readiness query.
- Alembic is configured under `apps/backend/alembic/` and reads the application database URL and `Base.metadata`. The initial revision is empty because no domain models exist yet; `supplylens/models/` is currently only a package placeholder.
- `apps/backend/tests/manual/` contains VS Code REST Client health checks. These are manual checks, not an automated test suite.
- `apps/web/` is a React 19, TypeScript 6, and Vite 8 starter. It does not yet implement a SupplyLens product workflow.
- `fixtures/` contains generated, synthetic PDF scenarios and `expected.json` for future extraction, reconciliation, provenance, OCR, and validation tests.
- `compose.yaml` runs PostgreSQL 17 with pgvector on host port `5433` using local-only development credentials.
- The root `Makefile` wraps dependency installation, development servers, frontend checks, backend syntax compilation, Alembic commands, and Docker Compose operations.
- Document ingestion, OCR, reviewed purchase records, catalog matching, pricing policies, reports, search, workers, authentication, and automated tests remain planned work.

## Project Structure and Module Organization

- `apps/backend/`: FastAPI package under `src/supplylens/`, Alembic configuration, and backend checks.
- `apps/web/`: React and TypeScript frontend; application code is in `src/` and static files are in `public/`.
- `docs/`: product definition and architecture references.
- `specifications/`: canonical, reusable process definitions intended for contributors and future automation skills.
- `fixtures/`: synthetic or anonymized document fixtures and expected results only.
- `infra/`: deployment and infrastructure configuration; currently a placeholder.
- `compose.yaml`: local PostgreSQL with pgvector.

Follow the modular backend layout proposed in the architecture document as features arrive. Keep API and worker entry points in the same `supplylens` package, and keep domain logic deterministic with provider-specific integrations behind adapters.

## Build, Test, and Development Commands

Run these from the repository root unless noted otherwise:

- `make setup`: install locked backend and frontend dependencies.
- `make be`: run the FastAPI development server.
- `make fe`: run the Vite development server.
- `make check`: compile backend Python and run frontend lint and build checks.
- `make db-revision MESSAGE="..."`: generate an Alembic revision.
- `make db-upgrade`: apply pending migrations.
- `make db-check`: check whether model changes require a migration.
- `make docker-start`: start Compose services.
- `docker compose up -d db`: start only the local database on port `5433`.

Equivalent direct commands include `uv sync` and `uv run uvicorn supplylens.api:app --reload` from `apps/backend`, plus `npm ci`, `npm run dev`, `npm run lint`, and `npm run build` from `apps/web`.

Copy `apps/backend/.env.example` to `apps/backend/.env` before commands that require `DATABASE_URL`. Never commit the resulting `.env` file.

## Coding Style and Naming Conventions

Use four spaces, type annotations, `snake_case` modules and functions, and `PascalCase` classes in Python. Follow the existing ESLint configuration in TypeScript, use two spaces, `PascalCase` React components, and `camelCase` variables and functions. Keep imports organized and avoid broad exception handling unless an application boundary deliberately translates the error.

Money, quantities, validation, provenance, and policy calculations must remain deterministic and auditable. Optional AI output is always a suggestion and must not silently become confirmed business data.

## Testing Guidelines

Automated suites are not yet scaffolded. Add backend tests in `apps/backend/tests/` using `pytest` and frontend tests beside components or under `apps/web/src/__tests__/`. Name Python tests `test_*.py`; name frontend tests `*.test.ts` or `*.test.tsx`.

Use only synthetic fixtures. Cover success, validation failure, provenance, database failure, immutable history, and the complete no-LLM behavior. Do not describe files under `apps/backend/tests/manual/` as automated coverage.

## Commit and Pull Request Guidelines

Use a clear PR title with exactly one lowercase commit prefix, such as `feat:`, `chore:`, `minor:`, `bug:`, `fix:`, `docs:`, `test:`, or `refactor:`. Prefer the format `<prefix>: [<JIRA-TICKET>] <imperative summary>` when a Jira ticket exists. Do not create commits or otherwise mutate Git history unless the developer explicitly requests it.

`specifications/pull-request-definition.md` is the canonical PR definition. Every PR description must contain `Summary`, `Testing` with separate `Unit testing` and `Manual testing` subsections, and `Rollback plan`. The developer remains responsible for approving the final scope and publication of every PR.
