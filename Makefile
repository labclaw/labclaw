.PHONY: lint format test test-integration test-mcp build dev-install clean

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

format:
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

test:
	PYTHONPATH=src uv run pytest -m "not integration and not mcp" --cov=labclaw --cov-fail-under=100 -q

test-integration:
	PYTHONPATH=src uv run pytest -m integration -v

test-mcp:
	PYTHONPATH=src uv run pytest -m mcp -v

build:
	uv run python -m build

dev-install:
	uv sync --extra dev --extra tooluniverse --extra llm

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .ruff_cache htmlcov .coverage
