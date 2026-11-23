# Order Resolution Crew: Design

Date: 2026-11-23
Status: approved (model changed to Gemini after approval)

## Intent

Build a CrewAI crew that customers of Acme Pte. Ltd. use to get details about their orders
and to find out whether an order can be refunded. The customer writes in plain English, for
example:

> "I'm Maria Anders from Alfreds Futterkiste and want to refund the order I purchased on
> 13 November."

The crew identifies the customer, finds the relevant order(s), and answers. For refund
requests it decides eligibility by reading the refund policy file
(`docs/refund-policy.md`) and explains why the order is or isn't eligible, and how much would
be refunded.

It's a support assistant: correct, careful answers matter more than flexibility.

## Goals

- Answer three kinds of requests in plain English:
  - **Order details**: one order's details, shipping information and items (product name,
    quantity, unit price, discount).
  - **Order search**: a customer's orders, optionally within a date range.
  - **Refund eligibility**: whether an order can be refunded under the policy, why or why
    not, and the refund amount.
- Make refund decisions by reading `docs/refund-policy.md` at request time. Editing that file
  changes the crew's decisions with no code change.
- Never show one customer's orders to another customer.
- Ask the customer for what's missing rather than guessing: an unknown customer, an
  ambiguous order, a date with no matching order.

## Non-goals

- **Issuing refunds.** The crew decides and explains only; a person processes the refund.
  Nothing is written to the database.
- **Authentication.** Customers identify themselves by name or customer ID; nothing proves
  they are who they say. Acceptable for this test database.
- **Langfuse tracing.** A likely next step, out of scope here.
- **Multi-turn conversation.** Each request is answered on its own. When information is
  missing, the answer says what to provide, and the customer sends a new, complete message.
- Fuzzy name matching, emails, membership tiers, item condition: the data has none of these.

## Anti-goals

These would make it a failure even if it otherwise works:

- Revealing any order, or even the existence of an order, belonging to a customer other than
  the one identified in the message.
- Approving a refund the policy doesn't allow, or refusing one it does, because of arithmetic
  or date errors.
- Refund rules hard-coded in Python instead of read from the policy file.
- Silently picking one order when several match the customer's description.

## Constraints and facts about the data

- Database: `data/northwind.db` (SQLite), path from the `NORTHWIND_DB_PATH` setting. Existing
  SQLAlchemy models in `src/langfuse_agent_demo/db/models.py`.
- **No emails.** Customers are identified by one of:
  - customer ID (e.g. `ALFKI`), unique;
  - contact name (e.g. `Maria Anders`), unique across all 93 customers;
  - contact name + company name, which must belong to the same customer.

  Company name alone is **not** unique (92 distinct names across 93 customers) and is not
  accepted on its own.
- Matching is exact after trimming whitespace and ignoring case. No fuzzy matching.
- Orders run from 2012-07-10 to 2023-10-28. 21 orders have no shipped date (not shipped).
  `OrderDate` and `ShippedDate` are stored with and without a time part; the models already
  handle both.
- There is no delivery date; the policy counts from the shipped date.
- `Products.Discontinued` reflects the product's status today, not at the time of the order.
- Test policy: `docs/refund-policy.md`. Every rule in it is checkable against the data.

## Approaches considered

- **A. Manager-led (hierarchical) crew — chosen.** CrewAI's hierarchical process: a manager
  agent reads the message and delegates to the three specialist agents as it sees fit.
  Handles unusual phrasing well and needs the least routing code. Trade-offs: routing is
  decided by the model, varies between runs, costs more model calls, and is harder to test.
- **B. Flow with an explicit routing step.** One model call extracts intent and identifiers
  into structured data; code runs the right agents in order. Predictable and testable, more
  code. Not chosen.
- **C. One fixed sequence** (search, then details, then refund) with agents skipping what
  doesn't apply. Simple but wasteful and awkward for plain detail requests. Not chosen.

Because the routing is left to the model in A, the safety-critical rules are enforced in the
tools, not in prompts (see "Tools").

## Decisions

### Agents

| Agent | Role | Tools |
| --- | --- | --- |
| Manager | Reads the customer's message, delegates to the specialists, writes the final answer. | none (CrewAI hierarchical manager) |
| Order details agent | Returns one order's details, shipping and items. | `get_order_details` |
| Order search agent | Lists a customer's orders, optionally within a date range. | `search_orders` |
| Refund policy agent | Decides refund eligibility for one order by applying the policy file to the order's facts; explains the decision and the amount. | `read_refund_policy`, `get_order_details`, `calculate_refund_amount` |

For a refund request without an order ID, the expected path is: search agent finds the
order(s) for the date given, then the refund policy agent assesses the single match. If
several orders match, the final answer lists them and asks the customer which one; if none
match, it says so.

### Tools

All tools are read-only Python functions over the existing SQLAlchemy models.

- **Customer identification is built into every order tool.** `get_order_details` and
  `search_orders` take the customer's identifiers (`customer_id`, `contact_name`,
  `company_name`, all optional) and resolve the customer themselves using the matching rules
  above. Without exactly one matching customer they return a "customer not found" result and
  no order data.
- **Order scoping.** `get_order_details(order_id, …)` returns the order only if it belongs to
  the identified customer. An order that exists but belongs to someone else returns exactly
  the same "order not found" result as a non-existent order.
- **Facts, not decisions.** `get_order_details` returns, in addition to stored data,
  pre-computed facts as of "today" (see Current date), so agents never do date or money
  arithmetic:
  - shipped yes/no; days since order date; days since shipped; shipped late (shipped date
    after required date) and days late;
  - per item: product ID, product name, category, quantity, unit price, discount,
    discontinued flag, item value (unit price × quantity × (1 − discount));
  - freight; order total (items + freight).

  It does **not** compute refund eligibility. That decision is the refund policy agent's,
  made from the policy file.

  *Builder's-check call:* policy edits are supported without code changes as long as the
  rules are built on these facts: changed windows, thresholds and percentages, or new rules
  using days since order, days late, category, discount or discontinued status. A rule that
  needs a fact not listed here (e.g. a supplier or a customer's country) needs a tool change.
- **`calculate_refund_amount(order_id, refundable_product_ids, include_freight, …)`** takes
  the customer identifiers like the other order tools, and returns the sum of the listed
  items' values plus freight if requested, with a per-item breakdown. The refund policy agent
  decides *which* items and whether freight are refundable from the policy; the tool only adds
  them up, so the amount is never produced by model arithmetic. *Builder's-check call.*
- **Discontinued status.** The flag is passed as-is and the policy's final-sale rule applies to
  a product's status today, even for old orders. This is a known limitation of the test data
  (the database only stores the current status), accepted for this test policy.
  *Builder's-check call.*
- **`search_orders(…, date_from?, date_to?)`** returns order summaries (order ID, order date,
  shipped date, item count, order total), newest first, inclusive of both dates, compared on
  the date part only.
- **`read_refund_policy()`** reads `docs/refund-policy.md` from disk on every call and returns
  its text.

### Current date

New optional setting `CURRENT_DATE` (ISO date) is "today" for the crew: for resolving
relative or year-less dates and for the policy's return windows. When unset, the real date is
used. `.env.example` sets it to a date close to the newest orders (e.g. `2023-11-20`), so the
demo data has orders inside the return windows.

A date without a year ("13 November") resolves to the most recent such date on or before
today. The manager and agents are told today's date in their task descriptions.

### Interface

New endpoint on the existing FastAPI app:

- `POST /orders/assist` with body `{"message": "<plain English>"}`.
- Response `200 {"answer": "<plain English>"}`. This includes "I couldn't find your
  account…" style answers; those are normal outcomes, not errors.
- If the crew fails (e.g. the model provider is unreachable), `503` with
  `{"error": "..."}`, details logged, not returned.

The crew runs synchronously; the endpoint is a plain `def` so FastAPI runs it in a thread
pool, like `/health`.

### Model

Google Gemini, for the manager and all agents, through CrewAI's native Gemini provider
(`crewai[google-genai]` extra; model names are `gemini/<model>`). Settings in `.env`:
`GEMINI_API_KEY` (required to run the crew) and `LLM_MODEL` (default
`gemini/gemini-2.5-flash`). Both go in `.env.example` (key left blank).

CrewAI 1.15 requires Python < 3.14, so `requires-python` becomes `>=3.13,<3.14`.

### Read-only database

Since nothing is written, the engine opens the database read-only (SQLite `mode=ro` instead
of the current `mode=rw`), so the crew cannot modify data even by mistake. `/health` keeps
working unchanged.

### Settings summary

| Setting | Required | Purpose |
| --- | --- | --- |
| `NORTHWIND_DB_PATH` | yes | existing |
| `REFUND_POLICY_PATH` | no, default `docs/refund-policy.md` | policy file the refund agent reads |
| `CURRENT_DATE` | no, default real date | the crew's "today" |
| `LLM_MODEL` | no, default `gemini/gemini-2.5-flash` | model for all agents |
| `GEMINI_API_KEY` | only to run the crew | Gemini API key |

`GEMINI_API_KEY` is not required at app startup, so `/health` and the tests that don't call
the model work without it.

### Testing

- **Tools**: unit tests against the real database with a fixed `CURRENT_DATE`: each
  customer-identification path, mismatched contact/company, wrong-customer order returns
  "not found", computed facts (days since shipped, late, item values), date-range search,
  refund amount sums (with and without freight, subset of items, product not on the order).
  These run in `make test`.
- **Endpoint**: tests with the crew replaced by a stub (success and failure → 503). Run in
  `make test`.
- **Crew end-to-end**: a handful of scenario tests against the real model (refund eligible,
  refund outside window, final-sale item, not shipped, unknown customer, several orders on
  one date). Marked so they're skipped in `make test` and run on demand, since they cost money
  and aren't deterministic.

## Left to the builder

- Module layout under `src/langfuse_agent_demo/` (e.g. `crew/agents.py`, `crew/tools.py`).
- CrewAI version, and how tools are declared (decorator vs. `BaseTool` subclasses).
- Agent role/goal/backstory wording and task descriptions, within the decisions above.
- Exact tool return format (JSON or text), as long as it carries the facts listed.
- The pytest marker name for live-model tests and how they're invoked (e.g. a `make` target).
- Upper limit on the number of orders `search_orders` returns, and how truncation is reported.
- Handling a message that gives a customer ID and a contact name that disagree (treat as no
  match, consistent with the contact/company rule), and rounding of money to cents.

## Data checks done during review

- No shipped date is later than the suggested `CURRENT_DATE` of 2023-11-20, so days since
  shipped is never negative.
- The 21 unshipped orders are from 2018.
- Customers do have several orders on one date (e.g. `ALFKI`), so the "ask which order" path
  is real.
- The highest discount is exactly 0.25, so the policy's "25% or more" boundary is exercised.
