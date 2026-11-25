.PHONY: install run test format prompts-push

install:
	uv sync

run:
	uv run fastapi dev

# Create the crew's prompts in Langfuse from crew/prompts.toml; ARGS=--force resets edited ones.
prompts-push:
	uv run python -m langfuse_agent_demo.crew.push_prompts $(ARGS)

# Static checks run first; make stops on the first failure, so pytest only runs if they pass.
test:
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy
	uv run pytest

format:
	uv run ruff check --fix .
	uv run ruff format .
