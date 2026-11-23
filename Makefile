.PHONY: install run lint format

install:
	uv sync

run:
	uv run fastapi dev

lint:
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy

format:
	uv run ruff check --fix .
	uv run ruff format .
