# ─── Totoro Agent — Common Commands ────────────────────
.PHONY: help install dev lint format typecheck test test-cov clean all

.DEFAULT_GOAL := help

## Show this help message
help:
	@echo "Totoro Agent — Available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

## Install all dependencies (dev)
install:
	uv sync

## Install pre-commit hooks
dev:
	pre-commit install
	@echo "✅ Pre-commit hooks installed"

## Run ruff linter
lint:
	uv run ruff check .

## Auto-fix lint issues
lint-fix:
	uv run ruff check . --fix

## Run ruff formatter
format:
	uv run ruff format .

## Check formatting without modifying
format-check:
	uv run ruff format . --check

## Run mypy type checker
typecheck:
	uv run mypy agent/ providers/ tools/ sandbox/ cli/ config.py api/

## Run all tests
test:
	uv run pytest -v

## Run tests with coverage report
test-cov:
	uv run pytest -v --cov=agent --cov=providers --cov=tools --cov=sandbox --cov=cli --cov-report=term-missing --cov-report=html

## Run tests (skip slow/integration)
test-fast:
	uv run pytest -v -m "not slow and not integration"

## Run lint + format check + typecheck + test (CI pipeline)
all: lint format-check typecheck test

## Clean build artifacts
clean:
	rm -rf .mypy_cache .ruff_cache .pytest_cache .coverage htmlcov
	rm -rf dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Cleaned"
