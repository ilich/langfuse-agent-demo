# Order assistant client

A small chat UI for testing the order assistant server ([`apps/server`](../server)), built with
[Vite](https://vite.dev), React, TypeScript and [assistant-ui](https://www.assistant-ui.com).

## Run

Start the server first (from `apps/server`: `make run`), then:

```bash
make install
make run        # http://localhost:5173
```

The Vite dev server proxies `/orders` and `/health` to `http://127.0.0.1:8000`, so the API needs
no CORS setup. Set `SERVER_URL` to point it elsewhere, e.g. `SERVER_URL=http://127.0.0.1:9000 make run`.

The header shows whether `GET /health` succeeds. The welcome screen lists the server README's
test prompts; click one to send it.

## How it talks to the server

assistant-ui's `useLocalRuntime` runs a small adapter (`src/adapter.ts`) that sends the latest
user message to `POST /orders/assist` and shows the `answer`. Errors (for example
`503 {"error": "..."}` when the model key is missing) appear under the reply.

The server answers each message on its own and keeps no conversation, so earlier turns are not
sent. Say who you are (customer ID or contact name) in every message.

## Tests

```bash
make test   # type-check (tsc), lint (oxlint), then unit tests (vitest)
```
