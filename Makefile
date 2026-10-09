.DEFAULT_GOAL := help

.PHONY: help setup hooks hooks-uninstall fe fe-install fe-build fe-lint be be-install be-check be-lint be-test be-test-integration version-test check db-revision db-upgrade db-downgrade db-current db-history db-check create-admin docker-start docker-stop docker-status docker-logs docker-test-start docker-test-stop docker-test-storage-start docker-test-storage-stop pre-commit

help: ## Show available commands
	@echo "SupplyLens development commands:"
	@echo "  make setup ....................... Install backend and frontend dependencies"
	@echo "  make hooks ....................... Install pre-push quality checks"
	@echo "  make hooks-uninstall ............. Remove the pre-push quality hook"
	@echo "  make fe .......................... Run the React development server"
	@echo "  make be .......................... Run the FastAPI development server"
	@echo "  make be-check .................... Check backend Python syntax"
	@echo "  make be-lint ..................... Run Ruff lint and formatting checks"
	@echo "  make be-test ..................... Run backend tests that do not require PostgreSQL"
	@echo "  make be-test-integration ......... Run storage and database integration tests"
	@echo "  make version-test ................ Run version automation tests"
	@echo "  make check ....................... Run backend and frontend checks"
	@echo "  make db-revision msg=... ......... Create an autogenerate migration"
	@echo "  make db-upgrade .................. Apply all pending migrations"
	@echo "  make create-admin ................ Create the local accepted admin user"
	@echo "  make db-downgrade ................ Roll back one migration"
	@echo "  make db-current .................. Show the current migration revision"
	@echo "  make db-history .................. Show migration history"
	@echo "  make db-check .................... Check for model changes without a migration"
	@echo "  make docker-start ................ Start Docker Compose services"
	@echo "  make docker-stop ................. Stop and remove Docker Compose services"
	@echo "  make docker-status ............... Show Docker Compose service status"
	@echo "  make docker-logs ................. Follow Docker Compose logs"
	@echo "  make docker-test-start ........... Start the disposable PostgreSQL test database"
	@echo "  make docker-test-stop ............ Remove the disposable PostgreSQL test database"
	@echo "  make docker-test-storage-start ... Start disposable test MinIO"
	@echo "  make docker-test-storage-stop .... Remove disposable test MinIO"
	@echo "  make prec | precommit | pre-commit Run pre-commit checks on all files"

hooks: ## Install the repository quality gate as a pre-push hook
	pre-commit uninstall
	pre-commit install --hook-type pre-push

hooks-uninstall: ## Remove the pre-push quality hook
	pre-commit uninstall --hook-type pre-push
	pre-commit uninstall

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
	cd apps/backend && uv sync --locked

be-check: ## Check backend Python syntax
	cd apps/backend && uv run python -m compileall -q src

be-lint: ## Run backend lint and formatting checks
	cd apps/backend && uv run ruff check .
	cd apps/backend && uv run ruff format --check .

be-test: ## Run backend tests that do not require PostgreSQL
	uv run --project apps/backend python scripts/check_coverage.py

be-test-integration: docker-test-start docker-test-storage-start ## Run storage and database integration tests
	cd apps/backend && uv run pytest -m integration tests/integration

version-test: ## Run version automation tests
	python -m unittest discover -s .github/scripts -p "test_*.py"

check: be-check be-lint be-test version-test fe-lint fe-build ## Run backend and frontend checks

db-revision: ## Create an autogenerate migration (use msg="...")
	$(if $(strip $(msg)),,$(error Usage: make db-revision msg="Add users table"))
	cd apps/backend && uv run alembic revision --autogenerate -m "$(msg)"

db-upgrade: ## Apply all pending Alembic migrations
	cd apps/backend && uv run alembic upgrade head

create-admin: ## Create the local accepted admin from ADMIN_USER_EMAIL and ADMIN_USER_PASSWORD
	uv run --project apps/backend python scripts/create_admin_user.py

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

docker-test-start: ## Start the disposable PostgreSQL test database
	docker compose --profile test up -d --wait db-test

docker-test-stop: ## Remove the disposable PostgreSQL test database
	docker compose --profile test rm --stop --force --volumes db-test

docker-test-storage-start: ## Start the disposable MinIO test service
	docker compose --profile test up -d --wait minio-test

docker-test-storage-stop: ## Remove the disposable MinIO test service
	docker compose --profile test rm --stop --force minio-test

prec precommit pre-commit: ## Run precommit agains all files
	pre-commit run --all-files
