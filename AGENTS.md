# Agent Guidelines

## Git workflow

- Do not create pull requests. Work directly on the `main` branch.
- Use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages:
  `<type>(<optional scope>): <description>`, e.g. `feat(health): add /health endpoint`.
  Common types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore`.

## Code quality

- Always run `make test` after making changes to ensure the code is correct.
  It checks formatting (ruff), lints (ruff), and type-checks (mypy), then runs the
  tests (pytest) only if all of those checks pass.
- If `make test` reports formatting issues, run `make format`, then run `make test` again.
