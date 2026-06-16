.PHONY: install lint typecheck test test-ci test-live demo demo-live clean

install:
	uv sync --extra dev

lint:
	uv run ruff format --check src/ tests/
	uv run ruff check src/ tests/

typecheck:
	uv run mypy src/

test: test-ci

test-ci:
	uv run pytest tests/ -v --tb=short -m "not live"

test-live:
	uv run pytest tests/ -v --tb=short

test-unit:
	uv run pytest tests/unit/ -v --tb=short

test-integration:
	uv run pytest tests/integration/ -v --tb=short

demo:
	HARNESS_FOUNDRY_MODEL=fake uv run harnessx-poc demo

demo-live:
	uv run harnessx-poc demo

api:
	uv run uvicorn harness_foundry.api.app:app --reload --host 0.0.0.0 --port 8000

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__ src/**/__pycache__ tests/**/__pycache__
	find . -type d -name __pycache__ -exec rm -rf {} +
