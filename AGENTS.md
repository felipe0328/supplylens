# Repository Guidelines

## Project Purpose

SupplyLens turns supplier purchase PDFs into reviewable, traceable purchase and product data for small retailers. The core workflow must work without an LLM; AI assistance is optional and must never replace validation, human confirmation, or deterministic calculations. Treat `docs/SupplyLens-MVP-Definition-v0.1.md` as the product-scope source of truth and `docs/SupplyLens-Architecture-v0.1.md` as the technical design reference. Keep real supplier data, credentials, and private pricing policies out of the repository.

## Project Structure & Module Organization

- `apps/backend/`: Python 3.14 FastAPI package under `src/supplylens/`; `api.py` currently exposes the health endpoint.
- `apps/web/`: React 19, TypeScript, and Vite frontend; application code lives in `src/`, static files in `public/`.
- `docs/`: MVP definition and architecture decisions.
- `fixtures/`: synthetic or anonymized document fixtures and expected results only.
- `infra/`: deployment and infrastructure configuration.
- `compose.yaml`: local PostgreSQL 17 with pgvector.

Follow the modular backend layout proposed in the architecture document as features arrive; keep API and worker entry points in the same `supplylens` package.

## Build, Test, and Development Commands

- `docker compose up -d db`: start the local pgvector database on port 5433.
- `cd apps/backend && uv sync`: create or update the locked Python environment.
- `cd apps/backend && uv run uvicorn supplylens.api:app --reload`: run the API locally.
- `cd apps/web && npm ci`: install the exact frontend dependency lock.
- `cd apps/web && npm run dev`: start the Vite development server.
- `cd apps/web && npm run build`: type-check and create a production build.
- `cd apps/web && npm run lint`: run ESLint.

## Coding Style & Naming Conventions

Use four spaces, type annotations, `snake_case` modules/functions, and `PascalCase` classes in Python. In TypeScript, follow the existing ESLint configuration, use two spaces, `PascalCase` React components, and `camelCase` variables/functions. Keep domain logic deterministic and provider-specific integrations behind adapters.

## Testing Guidelines

Automated suites are not yet scaffolded. Add backend tests in `apps/backend/tests/` using `pytest` and frontend tests beside components or under `apps/web/src/__tests__/`. Name Python tests `test_*.py`; name frontend tests `*.test.ts(x)`. Use only synthetic fixtures. Cover success, validation failure, provenance, and no-LLM behavior.

## Commit & Pull Request Guidelines

History currently uses Conventional Commits (for example, `feat: Initializing SupplyLens Monorepo`). Continue with concise `feat:`, `fix:`, `docs:`, `test:`, or `chore:` subjects. PRs should explain scope, verification commands, linked issues, and architecture or privacy impacts; include screenshots for visible UI changes.
