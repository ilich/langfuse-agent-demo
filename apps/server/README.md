# langfuse-agent-demo

A FastAPI service with a [CrewAI](https://www.crewai.com/) crew that answers customers'
plain-English questions about their orders and refunds for Acme Pte. Ltd., using the Northwind
SQLite database and OpenAI's `gpt-4o-mini` model.

The crew is hierarchical: a manager agent delegates to three specialists.

- **Order details specialist**: one order's dates, shipping details and items.
- **Order search specialist**: a customer's orders, optionally within a date range.
- **Refund policy specialist**: decides whether an order can be refunded by reading
  [`docs/refund-policy.md`](docs/refund-policy.md) on every request, and explains why.

The crew is read-only: it never changes the database or issues refunds. Customers identify
themselves by customer ID, contact name, or contact name plus company name.

## Setup

```bash
make install
cp .env.example .env   # then set OPENAI_API_KEY
```

Settings (in `.env`):

| Setting | Purpose |
| --- | --- |
| `NORTHWIND_DB_PATH` | Path to the Northwind SQLite database (required). |
| `CURRENT_DATE` | The crew's "today" (ISO date). Defaults to the real date; `.env.example` uses `2023-11-20`, close to the newest orders. |
| `REFUND_POLICY_PATH` | Refund policy the refund agent reads (default `docs/refund-policy.md`). |
| `LLM_MODEL` | CrewAI model name (default `openai/gpt-4o-mini`). |
| `OPENAI_API_KEY` | OpenAI API key; needed to run the crew, not to start the app. |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | Langfuse project keys; tracing is on only when both are set. |
| `LANGFUSE_BASE_URL` | Langfuse server (default `https://cloud.langfuse.com`, EU region). |
| `LANGFUSE_GATEWAY_HOST`, `LANGFUSE_GATEWAY_KEY` | Langfuse AI Gateway; when both are set, all model calls go through it and `OPENAI_API_KEY` / `LLM_MODEL` are not used. |
| `LANGFUSE_GATEWAY_MODEL` | Gateway model ID `<connection>:<model>` (default `google-ai-studio:gemini-2.5-flash`). |
| `CREW_VERBOSE` | `true` prints each agent step, delegation and tool call to the console (default `false`; `.env.example` sets `true`). |

## Run

```bash
make run
```

```bash
curl -s localhost:8000/orders/assist \
  -H 'Content-Type: application/json' \
  -d '{"message": "I am Karin Josephs from Toms Spezialitäten. Can I get a refund for order 12544?"}'
```

### Test prompt

A refund request for a late shipment:

```json
{
  "message": "I am Carine Schmitt from France Restauration. I want to refund order 14288. It arrived too late"
}
```

```bash
curl -s localhost:8000/orders/assist \
  -H 'Content-Type: application/json' \
  -d '{"message": "I am Carine Schmitt from France Restauration. I want to refund order 14288. It arrived too late"}'
```

With `CURRENT_DATE=2023-11-20`, order 14288 (customer `FRANR`) was required by 2023-11-16 and
shipped on 2023-11-19: 3 days late and 1 day ago. That puts it inside the policy's 30-day window
for late orders, so the crew should approve a refund of the refundable items plus freight.
Discontinued products are final sale and are excluded.

The response is `{"answer": "..."}`, or `503 {"error": "..."}` if the crew can't run.
`GET /health` checks that the database is accessible.

## Tracing with Langfuse

With `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` set, every `/orders/assist` request is
traced to [Langfuse](https://langfuse.com), following the
[CrewAI integration guide](https://langfuse.com/integrations/frameworks/crewai). At startup the
app creates the Langfuse client, checks the credentials (a failure is logged, not fatal) and
instruments CrewAI with OpenInference. Each request becomes one `order-assistant` trace, tagged
`order-assistant`, with the customer's message as input and the crew's answer as output. Under
it are spans for the crew run, the task, each agent and every tool call. Buffered spans are
flushed when the app shuts down.

### Langfuse AI Gateway

With `LANGFUSE_GATEWAY_HOST` and `LANGFUSE_GATEWAY_KEY` set, the crew sends every model call
through the [Langfuse AI Gateway](https://langfuse.com/integrations/model-providers/openai-gateway)
instead of calling OpenAI directly. CrewAI uses its OpenAI provider with base URL
`$LANGFUSE_GATEWAY_HOST/openai/v1` and the gateway key; the provider's API key lives in the gateway's
connection. The gateway records each call (model, tokens, cost, and prompts if its ingestion mode
is `FULL`). Each request carries the current span's `traceparent` header, so when Langfuse
tracing is also on, these model calls appear inside the same `order-assistant` trace as the
crew, agent and tool spans. To list the model IDs your key can use:

```bash
curl -s "$LANGFUSE_GATEWAY_HOST/openai/v1/models" -H "Authorization: Bearer $LANGFUSE_GATEWAY_KEY"
```

## Refund policy

Refund rules live only in [`docs/refund-policy.md`](docs/refund-policy.md). Edit the file to
change the crew's decisions; no code change is needed as long as the rules use facts the order
tools provide: order, required and shipped dates (with days since order, days since shipped
and days late), freight, and each item's category, unit price, quantity, discount and
discontinued status.

## Tests

```bash
make test   # format, lint, type-check, then unit and API tests (no model calls)
```
