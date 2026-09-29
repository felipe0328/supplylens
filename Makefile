.DEFAULT_GOAL := help

.PHONY: help setup fe fe-install fe-build fe-lint be be-install be-check check db-revision db-upgrade db-downgrade db-current db-history db-check docker-start docker-stop docker-status docker-logs

help: ## Show available commands
	@echo "SupplyLens development commands:"
	@echo "  make setup          Install backend and frontend dependencies"
	@echo "  make fe             Run the React development server"
	@echo "  make be             Run the FastAPI development server"
	@echo "  make be-check       Check backend Python syntax"
	@echo "  make check          Run backend and frontend checks"
	@echo "  make db-revision MESSAGE=\"...\" Create an autogenerate migration"
	@echo "  make db-upgrade     Apply all pending migrations"
	@echo "  make db-downgrade   Roll back one migration"
	@echo "  make db-current     Show the current migration revision"
	@echo "  make db-history     Show migration history"
	@echo "  make db-check       Check for model changes without a migration"
	@echo "  make docker-start   Start Docker Compose services"
	@echo "  make docker-stop    Stop and remove Docker Compose services"
	@echo "  make docker-status  Show Docker Compose service status"
	@echo "  make docker-logs    Follow Docker Compose logs"

setup: be-install fe-install ## Install all project dependencies

fe: ## Run the React development server
	cd apps/web && npm run dev

fe-install: ## Install exact frontend dependencies from package-lock.json
	cd apps/web && npm ci

fe-build: ## Type-check and build the frontend for production
	cd apps/web && npm run build

fe-lint: ## Lint the frontend
	cd apps/web && npm run lint

be: ## Run the FastAPI development server with reload enabled
	cd apps/backend && uv run uvicorn supplylens.api:app --reload

be-install: ## Sync the locked Python environment
	cd apps/backend && uv sync

be-check: ## Check backend Python syntax
	cd apps/backend && uv run python -m compileall -q src

check: be-check fe-lint fe-build ## Run backend and frontend checks

db-revision: ## Create an autogenerate migration (use MESSAGE="...")
	$(if $(strip $(MESSAGE)),,$(error Usage: make db-revision MESSAGE="Add users table"))
	cd apps/backend && uv run alembic revision --autogenerate -m "$(MESSAGE)"

db-upgrade: ## Apply all pending Alembic migrations
	cd apps/backend && uv run alembic upgrade head

db-downgrade: ## Roll back the latest Alembic migration
	cd apps/backend && uv run alembic downgrade -1

db-current: ## Show the current Alembic revision
	cd apps/backend && uv run alembic current

db-history: ## Show Alembic migration history
	cd apps/backend && uv run alembic history

db-check: ## Check for model changes missing from migrations
	cd apps/backend && uv run alembic check

docker-start: ## Start Docker Compose services in the background
	docker compose up -d

docker-stop: ## Stop and remove Docker Compose services
	docker compose down

docker-status: ## Show Docker Compose service status
	docker compose ps

docker-logs: ## Follow Docker Compose logs (Ctrl+C to exit)
	docker compose logs --follow
