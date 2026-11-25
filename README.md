# langfuse-agent-demo

A monorepo of demo apps for tracing AI agents with [Langfuse](https://langfuse.com).

| App | Description |
| --- | --- |
| [`apps/server`](apps/server) | FastAPI service with a CrewAI crew that answers customers' questions about their orders and refunds. |

## Make targets

Run from the repository root. Each one runs the same target in every app (`run` starts the server):

```bash
make install   # install dependencies
make test      # format check, lint, type-check, then tests
make format    # fix formatting and lint issues
make run       # start the server
```

Each app can also be run on its own from its folder; see its README.
