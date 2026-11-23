.PHONY: install run test test-llm format

install:
	uv sync

run:
	uv run fastapi dev

# Static checks run first; make stops on the first failure, so pytest only runs if they pass.
test:
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy
	uv run pytest

# Live tests against the real LLM (needs GEMINI_API_KEY); excluded from make test.
test-llm:
	uv run pytest -m llm -v

format:
	uv run ruff check --fix .
	uv run ruff format .
