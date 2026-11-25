# Agent Guidelines

## Repository layout

- This is a monorepo. Each app lives in its own folder under `apps/` with its own
  `pyproject.toml`, `uv.lock`, `Makefile` and `.env`:
  - `apps/server`: FastAPI service with the CrewAI order assistant.
- Run app commands (`uv`, `make`, `fastapi`) from the app's folder. The root `Makefile` runs
  `install`, `test` and `format` in every app.

## Git workflow

- Do not create pull requests. Work directly on the `main` branch.
- Use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages:
  `<type>(<optional scope>): <description>`, e.g. `feat(health): add /health endpoint`.
  Common types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore`.

## Code quality

- Always run `make test` (from the repository root, or from the app you changed) after making
  changes to ensure the code is correct. It checks formatting (ruff), lints (ruff), and
  type-checks (mypy), then runs the tests (pytest) only if all of those checks pass.
- If `make test` reports formatting issues, run `make format`, then run `make test` again.
