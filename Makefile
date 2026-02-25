.PHONY: test lint format build docker demo clean install dev-install coverage-html docs docs-serve release

test:
	uv run pytest --cov=labclaw --cov-report=term-missing --cov-fail-under=100 -q

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

format:
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

build:
	rm -rf dist
	uv build --sdist --wheel

docker:
	docker build -t labclaw .

demo:
	uv run python -m labclaw demo

clean:
	rm -rf dist/ build/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +

install:
	uv sync --frozen

dev-install:
	uv sync --extra dev --extra science --frozen

coverage-html:
	uv run pytest --cov=labclaw --cov-report=html -q

docs:
	uv run mkdocs build

docs-serve:
	uv run mkdocs serve

release:
	uv run cz bump
	git push origin main --tags
