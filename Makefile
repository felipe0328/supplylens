.DEFAULT_GOAL := help

.PHONY: help setup fe fe-install fe-build fe-lint be be-install check docker-start docker-stop docker-status docker-logs

help: ## Show available commands
	@echo "SupplyLens development commands:"
	@echo "  make setup          Install backend and frontend dependencies"
	@echo "  make fe             Run the React development server"
	@echo "  make be             Run the FastAPI development server"
	@echo "  make check          Run frontend linting and production build"
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

check: fe-lint fe-build ## Run the checks currently configured in the repository

docker-start: ## Start Docker Compose services in the background
	docker compose up -d

docker-stop: ## Stop and remove Docker Compose services
	docker compose down

docker-status: ## Show Docker Compose service status
	docker compose ps

docker-logs: ## Follow Docker Compose logs (Ctrl+C to exit)
	docker compose logs --follow
