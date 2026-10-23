# Run from inside WSL (or any Linux/macOS shell) with Docker available.
COMPOSE := docker compose -f infra/compose.yaml
EXEC := $(COMPOSE) exec -T

.PHONY: help demo up down logs ps reset-db sandbox-images migrate validate-problems sync-problems \
	seed test test-sandbox lint gen-api

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

demo: sandbox-images up migrate sync-problems seed ## First run: build everything, load problems and demo data
	@echo "Open http://localhost:8080 and log in as Bob, Chen or Dana."

up: ## Start the stack (rebuilds images when Dockerfiles or dependencies change)
	$(COMPOSE) up -d --build --renew-anon-volumes

down: ## Stop the stack
	$(COMPOSE) down

logs: ## Follow logs (make logs s=worker for one service)
	$(COMPOSE) logs -f $(s)

ps: ## Service status
	$(COMPOSE) ps

reset-db: ## Delete all data (drops the Postgres volume)
	$(COMPOSE) down -v

sandbox-images: ## Build the per-language sandbox images
	docker build -t dailycommit-sandbox-python:latest sandbox/images/python

migrate: ## Apply database migrations
	$(EXEC) api alembic upgrade head

validate-problems: ## Check problems/ and run reference solutions in the sandbox (no DB writes)
	$(EXEC) worker python -m dailycommit.problems validate

sync-problems: ## Validate problems/ and load them into the database
	$(EXEC) worker python -m dailycommit.problems sync

seed: ## Demo users, group (invite DEMO2026) and a week of history
	$(EXEC) api python -m dailycommit.seed

test: ## Backend unit tests (no Docker sandbox needed)
	$(EXEC) api pytest

test-sandbox: ## Adversarial sandbox tests (needs sandbox images)
	$(EXEC) worker pytest -m sandbox

lint: ## Ruff + TypeScript checks
	$(EXEC) api ruff check src tests alembic
	$(EXEC) api ruff format --check src tests alembic
	$(EXEC) web npx tsc --noEmit

gen-api: ## Regenerate web/src/lib/api/schema.ts from the FastAPI OpenAPI schema
	$(EXEC) api python -m dailycommit.api.openapi > web/openapi.json
	$(EXEC) web npx openapi-typescript openapi.json -o src/lib/api/schema.ts
