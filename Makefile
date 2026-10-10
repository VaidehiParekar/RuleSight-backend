# Convenience targets. GNU Make is optional: on Windows, the equivalent PowerShell commands are in
# README.md. Every target is a thin wrapper around the documented commands.

.DEFAULT_GOAL := help
.PHONY: help install db-up db-down db-reset migrate migrate-new backend-dev frontend-dev \
        test test-backend test-frontend lint format check

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

install: ## Install backend (uv) and frontend (npm) dependencies
	uv sync --locked
	cd ../frontend && npm ci

db-up: ## Start local PostgreSQL with pgvector
	docker compose up -d --wait db

db-down: ## Stop the local database (keeps data)
	docker compose down

db-reset: ## DELETE the local database volume and recreate it (destroys local data)
	docker compose down -v
	docker compose up -d --wait db

migrate: ## Apply all migrations to DATABASE_URL (from backend/.env)
	uv run alembic upgrade head

migrate-new: ## Create a migration: make migrate-new m="describe the change"
	uv run alembic revision --autogenerate -m "$(m)"

backend-dev: ## Run the API with auto-reload on http://127.0.0.1:8000
	uv run uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000

frontend-dev: ## Run the web app on http://localhost:5173
	cd ../frontend && npm run dev

test: test-backend test-frontend ## Run all unit tests

test-backend: ## Backend unit tests (no database required)
	uv run pytest -m "not integration"

test-frontend: ## Frontend unit tests
	cd ../frontend && npm test

lint: ## Lint and type-check everything
	uv run ruff check . && uv run ruff format --check . && uv run mypy
	cd ../frontend && npm run lint && npm run typecheck && npm run format:check

format: ## Auto-format code
	uv run ruff format . && uv run ruff check --fix .
	cd ../frontend && npm run format

check: lint test ## Everything CI runs, locally
