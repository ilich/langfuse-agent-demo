# langfuse-agent-demo

A FastAPI service with a [CrewAI](https://www.crewai.com/) crew that answers customers'
plain-English questions about their orders and refunds for Acme Pte. Ltd., using the Northwind
SQLite database and a Gemini model.

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
cp .env.example .env   # then set GEMINI_API_KEY
```

Settings (in `.env`):

| Setting | Purpose |
| --- | --- |
| `NORTHWIND_DB_PATH` | Path to the Northwind SQLite database (required). |
| `CURRENT_DATE` | The crew's "today" (ISO date). Defaults to the real date; `.env.example` uses `2023-11-20`, close to the newest orders. |
| `REFUND_POLICY_PATH` | Refund policy the refund agent reads (default `docs/refund-policy.md`). |
| `LLM_MODEL` | CrewAI model name (default `gemini/gemini-2.5-flash`). |
| `GEMINI_API_KEY` | Gemini API key; needed to run the crew, not to start the app. |

## Run

```bash
make run
```

```bash
curl -s localhost:8000/orders/assist \
  -H 'Content-Type: application/json' \
  -d '{"message": "I am Karin Josephs from Toms Spezialitäten. Can I get a refund for order 12544?"}'
```

The response is `{"answer": "..."}`, or `503 {"error": "..."}` if the crew can't run.
`GET /health` checks that the database is accessible.

## Refund policy

Refund rules live only in [`docs/refund-policy.md`](docs/refund-policy.md). Edit the file to
change the crew's decisions; no code change is needed as long as the rules use facts the order
tools provide: order, required and shipped dates (with days since order, days since shipped
and days late), freight, and each item's category, unit price, quantity, discount and
discontinued status.

## Tests

```bash
make test       # format, lint, type-check, then unit and API tests (no model calls)
make test-llm   # end-to-end scenarios against the real Gemini model (needs GEMINI_API_KEY)
```
