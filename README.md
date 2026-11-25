# langfuse-agent-demo

A monorepo of demo apps for tracing AI agents with [Langfuse](https://langfuse.com).

| App | Description |
| --- | --- |
| [`apps/server`](apps/server) | FastAPI service with a CrewAI crew that answers customers' questions about their orders and refunds. |
| [`apps/client`](apps/client) | Vite + React + assistant-ui chat interface for testing the server API. |

## Make targets

Run from the repository root. `install`, `test` and `format` run the same target in every app:

```bash
make install   # install dependencies
make test      # format check, lint, type-check, then tests
make format    # fix formatting and lint issues
make server    # start the server (http://localhost:8000)
make client    # start the chat UI (http://localhost:5173), in a second terminal
```

Each app can also be run on its own from its folder; see its README.
