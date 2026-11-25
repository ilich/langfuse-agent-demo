# Agent Guidelines

## Repository layout

- This is a monorepo. Each app lives in its own folder under `apps/` with its own `Makefile`:
  - `apps/server`: FastAPI service with the CrewAI order assistant (Python, uv; `pyproject.toml`,
    `uv.lock`, `.env`).
  - `apps/client`: Vite + React + TypeScript chat UI built with `@assistant-ui/react` for
    testing the server (npm; `package.json`, `package-lock.json`).
- Run app commands (`uv`, `npm`, `make`) from the app's folder. The root `Makefile` runs
  `install`, `test` and `format` in every app.

## Git workflow

- Feature branches and pull requests are allowed. Name branches `<type>/<short-description>`
  with a Conventional Commits type, e.g. `feat/prompt-management`. Small changes may still be
  committed directly to `main`.
- Open pull requests against `main` with `gh pr create`. The PR title follows the commit message
  convention below.
- Use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages:
  `<type>(<optional scope>): <description>`, e.g. `feat(health): add /health endpoint`.
  Common types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore`.

## Code quality

- Always run `make test` (from the repository root, or from the app you changed) after making
  changes to ensure the code is correct. For the server it checks formatting (ruff),
  lints (ruff), and type-checks (mypy), then runs pytest; for the client it type-checks (tsc),
  lints (oxlint), then runs vitest. Tests run only if the checks before them pass.
- If `make test` reports formatting issues, run `make format`, then run `make test` again.
