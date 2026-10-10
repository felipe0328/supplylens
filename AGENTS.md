# Repository Guidelines

## Agent Authorization and Git Boundaries

- Default to read-only work. If the developer asks for a review, explanation, diagnosis, opinion, or ideas, inspect the repository and report findings without modifying files.
- Modify files only when the developer explicitly asks for an implementation or names a file or artifact to update. Keep changes within that request; propose unrelated improvements instead of applying them.
- An explicit edit request authorizes only the edits needed for that request. It does not authorize staging, committing, pushing, opening a pull request, or changing unrelated work.
- Never stage AI-authored or AI-modified files unless the developer explicitly asks for those exact changes to be staged. Invoking the repository's create-PR skill is a narrow exception for verified whitespace- or formatting-only pre-commit fixes on PR-diff paths that were clean before hooks ran; commit only those exact paths separately, never amend, and preserve the existing Git index and developer-staged work.
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
- Unit and API tests are co-located with backend code under `apps/backend/src/`; `apps/backend/tests/integration/` contains Docker-backed PostgreSQL and MinIO integration tests, and `apps/backend/tests/manual/` contains VS Code REST Client health checks.
- `apps/web/` is a React 19, TypeScript 6, and Vite 8 starter. It does not yet implement a SupplyLens product workflow.
- `fixtures/` contains 12 generated, synthetic digital PDF scenarios and `expected.json` for future extraction, reconciliation, provenance, and validation tests.
- `compose.yaml` runs PostgreSQL 17 with pgvector on host port `5433` for development and a disposable `supplylens_test` database on port `5434` under the `test` profile.
- The root `Makefile` wraps locked dependency installation, development servers, backend lint/unit/integration tests, frontend checks, version tests, Alembic commands, and Docker Compose operations.
- Automatic extraction in the MVP supports digital PDFs with selectable text. Image-only or scanned PDFs are preserved, marked unsupported for automatic extraction, and sent to manual review.
- Document ingestion, reviewed purchase records, catalog matching, pricing policies, reports, search, workers, and authentication remain planned work.

## Project Structure and Module Organization

- `apps/backend/`: FastAPI package under `src/supplylens/`, Alembic configuration, and backend checks.
- `apps/web/`: React and TypeScript frontend; application code is in `src/` and static files are in `public/`.
- `docs/`: product definition and architecture references.
- `specifications/`: canonical, reusable process definitions intended for contributors and future automation skills.
- `fixtures/`: synthetic or anonymized document fixtures and expected results only.
- `infra/`: deployment and infrastructure configuration; currently a placeholder.
- `compose.yaml`: local PostgreSQL with pgvector.

Follow the modular backend layout proposed in the architecture document as features arrive. Keep API and worker entry points in the same `supplylens` package, and keep business rules deterministic with provider-specific integrations behind adapters.

`supplylens/domain/` holds shared type definitions only: enums, exception classes, and other data shapes. Do not put functions there, and do not add tests there. Put behavior in the module that owns it, with a co-located `*_test.py`. A rule shared by a controller and an adapter, such as whether a pending account is still inside its approval window, belongs in `supplylens/helpers/`, which both layers can import.

## Build, Test, and Development Commands

Run these from the repository root unless noted otherwise:

- `make setup`: install locked backend and frontend dependencies.
- `make be`: run the FastAPI development server.
- `make fe`: run the Vite development server.
- `make be-lint`: run Ruff lint and formatting checks.
- `make be-test`: run backend unit/API tests without Docker services.
- `make be-test-integration`: start disposable PostgreSQL and MinIO services and run only integration tests.
- `make docker-test-stop` and `make docker-test-storage-stop`: remove their corresponding disposable test services.
- `make version-test`: run isolated standard-library tests for version automation.
- `make check`: run backend syntax, lint, unit/API tests, version tests, and frontend lint/build checks.
- `make db-revision MESSAGE="..."`: generate an Alembic revision.
- `make db-upgrade`: apply pending migrations.
- `make db-check`: check whether model changes require a migration.
- `make docker-start`: start Compose services.
- `docker compose up -d db`: start only the local database on port `5433`.

Equivalent direct commands include `uv sync --locked` and `uv run uvicorn supplylens.api:app --reload` from `apps/backend`, plus `npm ci`, `npm run dev`, `npm run lint`, and `npm run build` from `apps/web`.

Copy the root `.env.example` to the root `.env` before commands that require `DATABASE_URL`. Never commit the resulting `.env` file.

## Coding Style and Naming Conventions

Use four spaces, type annotations, `snake_case` modules and functions, and `PascalCase` classes in Python. Follow the existing ESLint configuration in TypeScript, use two spaces, `PascalCase` React components, and `camelCase` variables and functions. Keep imports organized and avoid broad exception handling unless an application boundary deliberately translates the error.

Money, quantities, validation, provenance, and policy calculations must remain deterministic and auditable. Optional AI output is always a suggestion and must not silently become confirmed business data.

## Testing Guidelines

- Follow the scoped [Python unit-testing instructions](.github/instructions/python-unit-testing.instructions.md) for backend unit tests.
- Follow [apps/web/AGENTS.md](apps/web/AGENTS.md) for frontend conventions and tests.
- Integration-test guidance will be defined separately; do not treat it as part of the Python unit-testing rules.
- Use only synthetic fixtures, and do not describe manual checks as automated coverage.

## Commit and Pull Request Guidelines

Use a clear PR title with exactly one lowercase prefix, such as `feat:`, `fix:`, `minor:`, `major:`, `chore:`, `bug:`, `docs:`, `test:`, or `refactor:`. When a ticket exists, use `[<TICKET>] <prefix>: <imperative summary>`, where the ticket is the GitHub issue id that matches the branch (`M1_1` is `[M1.1]`). Do not create commits or otherwise mutate Git history unless the developer explicitly requests it.

`specifications/pull-request-definition.md` is the canonical PR definition. Every PR description must contain `Summary`, `Testing` with separate `Unit testing` and `Manual testing` subsections, and `Rollback plan`. The developer remains responsible for approving the final scope and publication of every PR.
