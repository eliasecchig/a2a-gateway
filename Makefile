.PHONY: install lint typecheck format spell test test-live run run-with-agent docker-build docker-run clean

SOURCES = gateway/ agent/ tests/ run.py

install: ## Install all dependencies (including dev)
	uv sync

lint: ## Run ruff linter and format checker
	uv run ruff check $(SOURCES)
	uv run ruff format --check $(SOURCES)

typecheck: ## Run ty type checker
	uv run ty check gateway/ agent/ run.py

format: ## Auto-format and fix lint issues
	uv run ruff format $(SOURCES)
	uv run ruff check --fix $(SOURCES)

spell: ## Run spell checker
	uv run codespell $(SOURCES)

test: ## Run offline test suite (147 tests)
	uv run pytest tests/ -v

test-live: ## Run live integration tests (needs credentials)
	uv run pytest -m live tests/live/ -v

check: lint typecheck spell test ## Run all checks (lint + typecheck + spell + tests)

run: ## Start the gateway
	uv run python run.py

run-with-agent: ## Start the gateway with the built-in test agent
	uv run python run.py --with-agent

docker-build: ## Build Docker image
	docker build -t a2a-gateway .

docker-run: ## Run Docker container (pass env vars with -e)
	docker run -p 8000:8000 a2a-gateway

clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .ruff_cache dist build

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
