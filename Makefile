.PHONY: install run test format

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

format:
	uv run ruff check --fix .
	uv run ruff format .
