# Langfuse prompt management for the order assistant

## Intent

Move every prompt out of `apps/server/src/langfuse_agent_demo/crew/crew.py` into Langfuse prompt
management, so prompts can be edited and versioned in Langfuse. This is an open source demo, so the
prompts must ship with the project and a setup script must load them into the user's own Langfuse
project.

## Goals

- All 11 prompt texts (task description, expected output, role/goal/backstory of the three agents)
  are fetched from Langfuse at runtime; `crew.py` holds no prompt text.
- The project ships the prompts in `apps/server/src/langfuse_agent_demo/crew/prompts.toml` (package data) and a setup command,
  `make prompts-push`, that creates them in Langfuse.
- Each trace records which prompt versions produced the answer.

## Non-goals / anti-goals

- No runtime fallback to the file (decided: approach B). If Langfuse is unavailable, the assistant
  is unavailable.
- The setup script must never overwrite prompt edits made in Langfuse unless asked to (`--force`).

## Approaches

- **A. Langfuse with fallback copies in code/file**: keeps answering when Langfuse is down, but two
  sources of truth that drift. Rejected by the user.
- **B. Langfuse required, file used only for setup (chosen)**: a true move; the SDK caches fetched
  prompts (60 s TTL), and failures surface as a clear 503.

## Design

- `crew/prompts.toml`: one key per Langfuse prompt name, text in Langfuse `{{var}}` syntax:
  `order-assistant/resolve-request` (`{{message}}`, `{{today}}`), `order-assistant/expected-answer`,
  `order-assistant/{details,search,refund}-agent/{role,goal,backstory}`. TOML (stdlib `tomllib`, no
  new dependency, good multi-line strings) is the builder's call.
- `crew/push_prompts.py`, run as `python -m langfuse_agent_demo.crew.push_prompts` (`make prompts-push`): creates each missing prompt as a text prompt with
  label `production`; existing prompts are skipped; `--force` creates a new `production` version
  where the file text differs from the current `production` text. Needs the Langfuse keys in `.env`.
- `crew/prompts.py` (runtime): fetches each prompt's `production` version via the Langfuse client,
  converts to CrewAI `{var}` syntax, and returns them for `build_crew`. Missing keys or a failed
  fetch raise `PromptsUnavailableError` naming the prompt and pointing at `make prompts-push`; the
  orders endpoint already maps that to 503.
- Tracing: the `order-assistant` span gets metadata listing each prompt's name and version.
- Tests stay offline with a fake Langfuse client; a test checks `prompts.toml` contains every prompt
  the crew requests and the task prompt uses only `message` and `today`.
- README setup gains the `make prompts-push` step.
