# Order Resolution Crew Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `POST /orders/assist` endpoint that answers plain-English order and refund questions
with a hierarchical CrewAI crew (Gemini) over the Northwind database, deciding refunds from
`docs/refund-policy.md`.

**Architecture:** A plain-Python `orders` package does all data access, customer matching,
date and money arithmetic (pure functions taking a SQLAlchemy `Session` and `today: date`).
Thin CrewAI tools in `crew/tools.py` wrap it and return JSON strings. `crew/crew.py` assembles
a hierarchical crew (manager + 3 specialists) and exposes `run_order_assistant(message) -> str`,
which the FastAPI router calls.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.1, pydantic-settings, CrewAI 1.15
(`crewai[google-genai]`, native Gemini provider), pytest, ruff, mypy (strict).

**Spec:** `docs/superpowers/specs/2026-11-23-order-resolution-crew-design.md`

## Global Constraints

- Nothing writes to the database; the engine opens SQLite with `mode=ro`.
- Refund rules live only in `docs/refund-policy.md`; no eligibility logic in Python.
- Agents never do date or money arithmetic; tools return computed facts and sums.
- Customer identification: `customer_id` alone, `contact_name` alone, or `contact_name` +
  `company_name`; company name alone is rejected; all identifiers given must belong to the same
  customer; matching is exact after `strip()` + `casefold()`; no fuzzy matching.
- An order belonging to another customer returns exactly the same result as a non-existent one.
- Money is `Decimal`, rounded to cents with `ROUND_HALF_UP`; item value =
  unit price × quantity × (1 − discount), rounded per item.
- Settings: `NORTHWIND_DB_PATH` (required), `REFUND_POLICY_PATH` (default
  `docs/refund-policy.md`), `CURRENT_DATE` (optional ISO date, default real date), `LLM_MODEL`
  (default `gemini/gemini-2.5-flash`), `GEMINI_API_KEY` (optional at startup; needed to run
  the crew).
- `requires-python = ">=3.13,<3.14"` (CrewAI 1.15 requires < 3.14).
- Tests that call the real model are marked `llm` and excluded from `make test`.
- `make test` must pass at the end of every task (ruff format, ruff check, mypy strict, pytest).
- Conventional Commits, committed directly on `main`.

## Review Focus

1. **Accented or differently-cased names** ("antonio moreno taquería", "ANTONIO MORENO"): must
   match `Antonio Moreno` / `Antonio Moreno Taquería`. SQLite `lower()` is ASCII-only, so
   matching is done in Python with `casefold()` — test in Task 2.
2. **Whitespace around IDs**, both in input (`" alfki "`) and in the data (customer ID `"Val2 "`
   exists): must match after stripping — test in Task 2.
3. **Identifiers from two different customers** (customer ID `ALFKI` + contact name
   `Paul Henriot`): must be "not found", never either customer — test in Task 2.
4. **Inverted date range** (`date_from` after `date_to`): the tool returns a clear error the
   agent can act on, not an empty list that reads as "no orders" — test in Task 6.
5. **Policy file missing or unreadable**: `read_refund_policy` returns an error result so the
   crew says it can't decide, instead of the request failing — test in Task 6.

## Test fixtures (from `data/northwind.db`, "today" = 2023-11-20)

| Order | Customer (ID / contact / company) | Facts |
| --- | --- | --- |
| 10248 | VINET / Paul Henriot / Vins et alcools Chevalier | shipped 2016-07-16, required 2016-08-01, freight 16.75; items: 11 Queso Cabrales 14.00×12 = 168.00; 42 Singaporean Hokkien Fried Mee 9.80×10 = 98.00 (discontinued); 72 Mozzarella di Giovanni 34.80×5 = 174.00; items total 440.00 |
| 10250 | HANAR / Mario Pontes / Hanari Carnes | items: 41 → 77.00; 51 (disc 0.15) 42.40×35 → 1261.40; 65 (disc 0.15) 16.80×15 → 214.20; items total 1552.60; freight 25.00 |
| 12544 | TOMSP / Karin Josephs / Toms Spezialitäten | ordered 2023-10-09 11:26:49, required 2023-10-26, shipped 2023-11-01 00:34:03 → late by 6 days, 19 days since shipped, 42 days since order; one item 27 Schoggi Schokolade 43.90×12 = 526.80; freight 13.00 |
| 11008 | ERNSH / Roland Mendel / Ernst Handel | not shipped (ordered 2018-04-08); freight 55.25 |
| 13789 | MORGK / Alexander Feuer | shipped 2023-11-18 on time; 65 items, 6 discontinued |
| 11184 | MAISD / Catherine Dewey | shipped 2023-10-15 on time (36 days → outside 14-day window) |
| 23052, 26502 | LAZYK / John Steel / Lazy K Kountry Store | both ordered 2023-10-03 |

VINET has 158 orders; two of them (10248, 16165) are dated July 2016.

---

### Task 1: Settings, dependencies, read-only database

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `Makefile`, `.env.example`
- Modify: `src/langfuse_agent_demo/config.py`
- Modify: `src/langfuse_agent_demo/db/session.py`
- Modify: `tests/conftest.py` (add `db_session` fixture; move it from `tests/test_db_models.py`)
- Test: `tests/test_config.py`, `tests/test_db_session.py`

**Interfaces:**
- Produces: `Settings.refund_policy_path: Path`, `Settings.current_date: date | None`,
  `Settings.llm_model: str`, `Settings.gemini_api_key: SecretStr | None`;
  `get_today() -> date` in `config.py`; pytest fixture `db_session -> Iterator[Session]`
  (depends on `northwind_db`).

- [ ] **Step 1: Dependencies and tooling.** Set `requires-python = ">=3.13,<3.14"`, run
  `uv add "crewai[google-genai]"` (expect crewai 1.15.x; pydantic resolves to 2.12.x). Add to
  `pyproject.toml`:
  `[tool.pytest.ini_options]` with `markers = ["llm: calls the real LLM; run with make test-llm"]`
  and `addopts = "-m 'not llm'"`. Add Makefile target `test-llm: uv run pytest -m llm -v`
  (and to `.PHONY`). If mypy reports missing stubs for crewai, add a `[[tool.mypy.overrides]]`
  with `ignore_missing_imports = true` for `crewai.*` only.
- [ ] **Step 2: Write failing tests** in `tests/test_config.py` (clear `get_settings` cache in
  a fixture; use `monkeypatch.setenv`):
  - `test_today_uses_current_date_setting`: `CURRENT_DATE=2023-11-20` → `get_today() == date(2023, 11, 20)`.
  - `test_today_defaults_to_real_date`: `CURRENT_DATE` unset → `get_today() == date.today()`.

  Isolate these tests from the developer's `.env` (which sets `CURRENT_DATE`): in the fixture,
  `monkeypatch.chdir(tmp_path)` so no `.env` is found, `monkeypatch.setenv("NORTHWIND_DB_PATH", ...)`,
  and `monkeypatch.delenv` the optional settings.
  - `test_defaults`: `llm_model == "gemini/gemini-2.5-flash"`,
    `refund_policy_path == Path("docs/refund-policy.md")`, `gemini_api_key is None` when unset.

  And `tests/test_db_session.py::test_engine_is_read_only` (uses `northwind_db`): executing
  `text("CREATE TABLE _probe (x INTEGER)")` on `get_engine()` raises
  `sqlalchemy.exc.OperationalError` whose message contains `"readonly"`.
- [ ] **Step 3: Run** `uv run pytest tests/test_config.py tests/test_db_session.py -v` — expect
  FAIL (missing attributes / table created).
- [ ] **Step 4: Implement.** Add the four settings fields with the defaults above; `get_today()`
  returns `get_settings().current_date or date.today()`. Change the engine URL to `mode=ro`
  (update the comment). Add `CURRENT_DATE=2023-11-20`, `REFUND_POLICY_PATH=docs/refund-policy.md`,
  `LLM_MODEL=gemini/gemini-2.5-flash` and `GEMINI_API_KEY=` to `.env.example` with one comment
  line each; update your local `.env` the same way. Move the `session` fixture from
  `tests/test_db_models.py` into `conftest.py` as `db_session` and update that file.
- [ ] **Step 5: Run** `make test` — expect all green.
- [ ] **Step 6: Commit** `feat(config): add crew settings, crewai dependency and read-only database`

### Task 2: Customer identification

**Files:**
- Create: `src/langfuse_agent_demo/orders/__init__.py`, `src/langfuse_agent_demo/orders/customers.py`
- Test: `tests/orders/test_customers.py`

**Interfaces:**
- Produces (in `orders/customers.py`):
  - `class CustomerRef(BaseModel)`: `customer_id: str | None = None`,
    `contact_name: str | None = None`, `company_name: str | None = None`.
  - `class CustomerNotFoundError(Exception)`.
  - `resolve_customer(session: Session, ref: CustomerRef) -> Customer` — raises
    `CustomerNotFoundError` unless exactly one customer matches every identifier given.

- [ ] **Step 1: Write failing tests** (all use `db_session`):
  - `test_by_customer_id`: `CustomerRef(customer_id="ALFKI")` → `.customer_id == "ALFKI"`.
  - `test_by_contact_name`: `contact_name="Maria Anders"` → `ALFKI`.
  - `test_by_contact_and_company`: `"Maria Anders"` + `"Alfreds Futterkiste"` → `ALFKI`.
  - `test_case_whitespace_and_accents`: `contact_name="  ANTONIO MORENO "`,
    `company_name="antonio moreno taquería"` → `ANTON`; `customer_id=" alfki "` → `ALFKI`.
  - `test_stored_id_with_trailing_space`: `customer_id="Val2"` → customer whose
    `customer_id == "Val2 "`.
  - `test_company_alone_rejected`: `company_name="Alfreds Futterkiste"` → raises.
  - `test_mismatched_identifiers_rejected`: (`"Maria Anders"`, `"Hanari Carnes"`) raises;
    (`customer_id="ALFKI"`, `contact_name="Paul Henriot"`) raises.
  - `test_unknown_and_empty`: `contact_name="Nobody Here"` raises; `CustomerRef()` raises;
    `customer_id="   "` raises.
- [ ] **Step 2: Run** `uv run pytest tests/orders/test_customers.py -v` — expect FAIL (import error).
- [ ] **Step 3: Implement `resolve_customer`.** Normalise each given identifier with
  `strip().casefold()` (blank → treated as not given). Require `customer_id` or `contact_name`.
  Load all customers (93 rows) and filter in Python, comparing normalised values — do not use
  SQL `lower()`, it is ASCII-only. Exactly one match → return it; otherwise raise.
- [ ] **Step 4: Run** `make test` — expect green.
- [ ] **Step 5: Commit** `feat(orders): identify customers by ID, contact name or contact and company`

### Task 3: Order details with computed facts

**Files:**
- Create: `src/langfuse_agent_demo/orders/schemas.py`, `src/langfuse_agent_demo/orders/queries.py`
- Test: `tests/orders/test_order_details.py`

**Interfaces:**
- Consumes: `CustomerRef`, `resolve_customer`, `CustomerNotFoundError` (Task 2).
- Produces:
  - `orders/schemas.py`:
    - `OrderItem(BaseModel)`: `product_id: int`, `product_name: str`, `category: str | None`,
      `quantity: int`, `unit_price: Decimal`, `discount: float`, `discontinued: bool`,
      `value: Decimal`.
    - `OrderDetails(BaseModel)`: `order_id: int`, `customer_id: str`, `company_name: str | None`,
      `order_date: date | None`, `required_date: date | None`, `shipped_date: date | None`,
      `shipped: bool`, `days_since_order: int | None`, `days_since_shipped: int | None`,
      `shipped_late: bool | None`, `days_late: int | None`, `shipper: str | None`,
      `ship_name`, `ship_address`, `ship_city`, `ship_region`, `ship_postal_code`,
      `ship_country` (all `str | None`), `freight: Decimal`, `items_total: Decimal`,
      `order_total: Decimal`, `items: list[OrderItem]`.
  - `orders/queries.py`:
    - `class OrderNotFoundError(Exception)` with attribute `order_id: int`.
    - `get_order_details(session: Session, ref: CustomerRef, order_id: int, today: date) -> OrderDetails`.
    - `item_value(unit_price: Decimal, quantity: int, discount: float) -> Decimal`.

- [ ] **Step 1: Write failing tests** (`TODAY = date(2023, 11, 20)`):
  - `test_details_items_and_totals`: order 10248 for `customer_id="VINET"` → 3 items;
    item 42 has `product_name == "Singaporean Hokkien Fried Mee"`, `discontinued is True`,
    `category == "Grains/Cereals"`, `value == Decimal("98.00")`;
    `items_total == Decimal("440.00")`, `freight == Decimal("16.75")`,
    `order_total == Decimal("456.75")`, `shipped is True`, `shipped_late is False`,
    `days_late == 0`, `days_since_shipped == (TODAY - date(2016, 7, 16)).days`,
    `ship_city == "Reims"`, `shipper` is not None.
  - `test_discounted_item_value`: order 10250 / `HANAR` → item 51 `value == Decimal("1261.40")`,
    `discount == 0.15`; `items_total == Decimal("1552.60")`.
  - `test_late_shipment_with_time_parts`: order 12544 / `contact_name="Karin Josephs"` →
    `shipped_late is True`, `days_late == 6`, `days_since_shipped == 19`,
    `days_since_order == 42`, `shipped_date == date(2023, 11, 1)`.
  - `test_unshipped_order`: order 11008 / `ERNSH` → `shipped is False`,
    `shipped_date is None`, `days_since_shipped is None`, `shipped_late is None`,
    `days_late is None`.
  - `test_other_customers_order_not_found`: order 10248 for `ALFKI` raises
    `OrderNotFoundError`; order 99999999 for `ALFKI` raises `OrderNotFoundError`
    (same type, `order_id` set).
  - `test_unknown_customer`: `contact_name="Nobody Here"` raises `CustomerNotFoundError`.
- [ ] **Step 2: Run** `uv run pytest tests/orders/test_order_details.py -v` — expect FAIL.
- [ ] **Step 3: Implement.** `item_value` quantizes to `Decimal("0.01")` with `ROUND_HALF_UP`,
  converting `discount` via `Decimal(str(discount))`. Dates compare on `.date()` parts:
  `days_late = max(0, (shipped - required).days)`, `shipped_late = shipped > required`.
  Load the order with `selectinload` for items → product → category, and shipper; query by
  `order_id` **and** the resolved customer's `customer_id`.
- [ ] **Step 4: Run** `make test` — expect green.
- [ ] **Step 5: Commit** `feat(orders): return order details with computed refund facts`

### Task 4: Order search

**Files:**
- Modify: `src/langfuse_agent_demo/orders/schemas.py`, `src/langfuse_agent_demo/orders/queries.py`
- Test: `tests/orders/test_search_orders.py`

**Interfaces:**
- Produces:
  - `OrderSummary(BaseModel)`: `order_id: int`, `order_date: date | None`,
    `shipped_date: date | None`, `item_count: int`, `order_total: Decimal`.
  - `OrderSearchResult(BaseModel)`: `customer_id: str`, `total_matches: int`,
    `orders: list[OrderSummary]` (newest first, at most `limit`).
  - `class InvalidDateRangeError(ValueError)`.
  - `search_orders(session: Session, ref: CustomerRef, date_from: date | None = None, date_to: date | None = None, limit: int = 50) -> OrderSearchResult`.

- [ ] **Step 1: Write failing tests:**
  - `test_search_by_date_range`: `VINET`, 2016-07-01..2016-07-31 → `total_matches == 2`,
    order IDs `{10248, 16165}`, newest first; 10248's `order_total == Decimal("456.75")`,
    `item_count == 3`.
  - `test_single_day_inclusive_with_time_parts`: `LAZYK`, 2023-10-03..2023-10-03 →
    IDs `{23052, 26502}`.
  - `test_no_range_and_limit`: `VINET`, no dates, `limit=5` → `total_matches == 158`,
    `len(orders) == 5`, dates non-increasing.
  - `test_inverted_range`: `date_from=date(2023, 1, 2)`, `date_to=date(2023, 1, 1)` raises
    `InvalidDateRangeError`.
  - `test_unknown_customer`: raises `CustomerNotFoundError`.
- [ ] **Step 2: Run** `uv run pytest tests/orders/test_search_orders.py -v` — expect FAIL.
- [ ] **Step 3: Implement.** Filter on `func.date(Order.order_date)` against ISO strings so
  values with and without a time part compare correctly; count matches before limiting;
  compute `order_total` with `item_value` + freight (reuse, don't duplicate).
- [ ] **Step 4: Run** `make test` — expect green.
- [ ] **Step 5: Commit** `feat(orders): search a customer's orders by date range`

### Task 5: Refund amount calculation

**Files:**
- Modify: `src/langfuse_agent_demo/orders/schemas.py`, `src/langfuse_agent_demo/orders/queries.py`
- Test: `tests/orders/test_refund_amount.py`

**Interfaces:**
- Produces:
  - `RefundLine(BaseModel)`: `product_id: int`, `product_name: str`, `value: Decimal`.
  - `RefundCalculation(BaseModel)`: `order_id: int`, `lines: list[RefundLine]`,
    `items_total: Decimal`, `freight: Decimal` (0.00 when not included), `total: Decimal`.
  - `class ProductNotOnOrderError(Exception)` with `order_id: int`, `product_ids: list[int]`.
  - `calculate_refund_amount(session: Session, ref: CustomerRef, order_id: int, refundable_product_ids: list[int], include_freight: bool) -> RefundCalculation`.

- [ ] **Step 1: Write failing tests** (order 10248 / `VINET`):
  - `test_subset_without_freight`: products `[11, 72]`, `include_freight=False` →
    `items_total == Decimal("342.00")`, `freight == Decimal("0.00")`, `total == Decimal("342.00")`,
    2 lines.
  - `test_all_with_freight`: `[11, 42, 72]`, `True` → `total == Decimal("456.75")`.
  - `test_duplicates_ignored`: `[11, 11]`, `False` → `total == Decimal("168.00")`, 1 line.
  - `test_freight_only`: `[]`, `True` → `total == Decimal("16.75")`.
  - `test_product_not_on_order`: `[11, 999]` raises `ProductNotOnOrderError` with
    `product_ids == [999]`.
  - `test_other_customers_order`: `ALFKI` raises `OrderNotFoundError`.
- [ ] **Step 2: Run** `uv run pytest tests/orders/test_refund_amount.py -v` — expect FAIL.
- [ ] **Step 3: Implement** by reusing `get_order_details` (it already scopes to the customer
  and computes item values); `today` is irrelevant here, pass `date.today()` internally.
- [ ] **Step 4: Run** `make test` — expect green.
- [ ] **Step 5: Commit** `feat(orders): calculate refund amounts for chosen items`

### Task 6: CrewAI tools

**Files:**
- Create: `src/langfuse_agent_demo/crew/__init__.py`, `src/langfuse_agent_demo/crew/tools.py`
- Test: `tests/crew/test_tools.py`

**Interfaces:**
- Consumes: Tasks 2–5; `get_today()`, `get_settings()` (Task 1); `get_sessionmaker()`.
- Produces: module-level CrewAI tools created with `crewai.tools.tool`, named exactly
  `get_order_details`, `search_orders`, `calculate_refund_amount`, `read_refund_policy`,
  exported as `get_order_details_tool`, `search_orders_tool`, `calculate_refund_amount_tool`,
  `read_refund_policy_tool`. Every tool returns a JSON string: the pydantic model's
  `model_dump_json()` on success, `{"error": "<message>"}` on a known failure.
  Parameters:
  - order tools: `customer_id: str | None = None`, `contact_name: str | None = None`,
    `company_name: str | None = None`, plus:
    - `get_order_details`: `order_id: int`
    - `search_orders`: `date_from: str | None = None`, `date_to: str | None = None` (ISO dates)
    - `calculate_refund_amount`: `order_id: int`, `refundable_product_ids: list[int]`,
      `include_freight: bool`
  - `read_refund_policy`: no parameters; returns `{"policy": "<file text>"}`.
  Tool docstrings tell the agent what each returns and that dates are ISO `YYYY-MM-DD`.
- Error messages (exact):
  - customer: `"No customer matches the details given. Ask the customer for their customer ID, or their contact name and company name."`
  - order: `"Order {order_id} was not found for this customer."`
  - products: `"Products {ids} are not on order {order_id}."`
  - date range: `"date_from must be on or before date_to."`
  - bad date string: `"Dates must be in YYYY-MM-DD format."`
  - policy: `"The refund policy is unavailable, so refund eligibility cannot be decided."`

- [ ] **Step 1: Write failing tests** (call `tool.run(**kwargs)`, parse with `json.loads`;
  set `CURRENT_DATE=2023-11-20` via `monkeypatch` + `get_settings.cache_clear()`):
  - `test_get_order_details_tool`: order 12544 / `contact_name="Karin Josephs"` →
    `days_late == 6`, `days_since_shipped == 19`.
  - `test_not_found_is_identical_for_foreign_and_missing_orders`: for `ALFKI`, order 10248
    (exists, belongs to VINET) → `{"error": "Order 10248 was not found for this customer."}`;
    order 99999999 → `{"error": "Order 99999999 was not found for this customer."}`.
  - `test_unknown_customer_tool`: error equals the exact customer message.
  - `test_search_tool_dates_and_errors`: `VINET` 2016-07-01..2016-07-31 → `total_matches == 2`;
    inverted range → date-range error; `date_from="13 November"` → bad-date error.
  - `test_refund_tool`: 10248 / `VINET` / `[11, 72]` / `False` → `total == "342.00"`;
    `[999]` → products error.
  - `test_read_refund_policy_reads_file_each_call`: point `REFUND_POLICY_PATH` at a `tmp_path`
    file, read, change the file, read again → second result has the new text.
  - `test_read_refund_policy_missing_file`: nonexistent path → policy error.
- [ ] **Step 2: Run** `uv run pytest tests/crew/test_tools.py -v` — expect FAIL.
- [ ] **Step 3: Implement.** Each tool opens a session with `with get_sessionmaker()() as session:`,
  builds `CustomerRef`, calls the `orders` function, and maps the exceptions above to the error
  messages. Parse dates with `date.fromisoformat`. `read_refund_policy` reads
  `get_settings().refund_policy_path` on every call (catch `OSError`).
- [ ] **Step 4: Run** `make test` — expect green.
- [ ] **Step 5: Commit** `feat(crew): add order and refund policy tools for agents`

### Task 7: Crew assembly

**Files:**
- Create: `src/langfuse_agent_demo/crew/crew.py`
- Test: `tests/crew/test_crew.py`

**Interfaces:**
- Consumes: Task 6 tools; `get_settings()`, `get_today()`.
- Produces:
  - `class AssistantUnavailableError(RuntimeError)`.
  - `make_llm() -> LLM` — `LLM(model=settings.llm_model, api_key=<secret value>)`; raises
    `AssistantUnavailableError` if `gemini_api_key` is unset. (Pass the key explicitly:
    pydantic-settings does not export `.env` values to `os.environ`.)
  - `build_crew(llm: LLM) -> Crew`.
  - `run_order_assistant(message: str) -> str` — builds the crew, calls
    `crew.kickoff(inputs={"message": message, "today": get_today().isoformat()})`, returns
    `.raw`.

- [ ] **Step 1: Write failing tests** (no model calls; build with
  `LLM(model="gemini/gemini-2.5-flash", api_key="test-key")`):
  - `test_crew_structure`: `crew.process == Process.hierarchical`; `crew.manager_llm` set;
    three agents whose tool-name sets are exactly `{"get_order_details"}`, `{"search_orders"}`,
    `{"read_refund_policy", "get_order_details", "calculate_refund_amount"}`; all three have
    `allow_delegation is False`; one task whose description contains `"{message}"` and
    `"{today}"`.
  - `test_make_llm_requires_key`: no `GEMINI_API_KEY` → `AssistantUnavailableError`.
- [ ] **Step 2: Run** `uv run pytest tests/crew/test_crew.py -v` — expect FAIL.
- [ ] **Step 3: Implement.** Agent roles: "Order details specialist", "Order search
  specialist", "Refund policy specialist" (goals/backstories are yours). The single task's
  description must instruct, in this order:
  1. today is `{today}`; resolve year-less dates to the most recent such date on or before today;
  2. identify the customer only from identifiers in `{message}` and pass them unchanged to tools;
     if a tool says the customer isn't found, ask for the customer ID and stop;
  3. for refunds without an order ID, search first; if several orders match, list them and ask
     which one; if none, say so;
  4. refund decisions must come from the refund policy specialist, who reads the policy with
     `read_refund_policy`, applies it to the facts from `get_order_details`, and gets the amount
     from `calculate_refund_amount` — no rules from memory, no arithmetic;
  5. the answer must say whether the order is eligible, which policy rules decided it, and the
     amount; never mention other customers' data.
  Literal braces other than `{message}` and `{today}` must not appear in the description
  (CrewAI interpolates them).
- [ ] **Step 4: Run** `make test` — expect green.
- [ ] **Step 5: Commit** `feat(crew): assemble hierarchical order resolution crew`

### Task 8: `POST /orders/assist` endpoint

**Files:**
- Create: `src/langfuse_agent_demo/routers/orders.py`
- Modify: `src/langfuse_agent_demo/main.py`
- Test: `tests/test_orders_endpoint.py`

**Interfaces:**
- Consumes: `run_order_assistant` (Task 7).
- Produces: `AssistRequest(BaseModel)`: `message: str` (`min_length=1`, `max_length=2000`,
  whitespace stripped); `AssistResponse(BaseModel)`: `answer: str`;
  dependency `get_assistant() -> Callable[[str], str]` returning `run_order_assistant`.

- [ ] **Step 1: Write failing tests** (override `get_assistant` with stubs):
  - `test_assist_returns_answer`: stub returns `"ok"` and records its input → `200`,
    `{"answer": "ok"}`, stub received the message.
  - `test_assist_failure_is_503`: stub raises `RuntimeError("boom")` → `503`,
    `{"error": "The order assistant is unavailable. Please try again later."}`, and `"boom"`
    is not in the body.
  - `test_assist_rejects_empty_message`: `{"message": "   "}` → `422`.
- [ ] **Step 2: Run** `uv run pytest tests/test_orders_endpoint.py -v` — expect FAIL.
- [ ] **Step 3: Implement** as a plain `def` route (thread pool, like `/health`); on any
  exception log with `logger.exception` and return `JSONResponse(status_code=503, ...)`.
  Include the router in `main.py`.
- [ ] **Step 4: Run** `make test` — expect green.
- [ ] **Step 5: Commit** `feat(orders): add POST /orders/assist endpoint`

### Task 9: Live scenario tests and README

**Files:**
- Create: `tests/live/test_order_assistant_live.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `run_order_assistant` (Task 7).

- [ ] **Step 1: Write the live tests**, all `@pytest.mark.llm`, skipped when `GEMINI_API_KEY`
  is not configured, with `CURRENT_DATE=2023-11-20`. Assertions are on robust content only
  (case-insensitive substrings), since wording varies:
  - `test_late_order_refund`: "I'm Karin Josephs from Toms Spezialitäten, can I get a refund
    for order 12544?" → mentions `12544` and `539.80`.
  - `test_outside_window`: "Catherine Dewey here, please refund order 11184" → contains
    `"not eligible"` or `"cannot"`; does not contain `"eligible for a refund of"`. (Adjust the
    phrase list to what the answers actually use, keeping the intent: refusal.)
  - `test_unshipped_cancellation`: "Roland Mendel, Ernst Handel: refund order 11008" →
    mentions `4736.15`.
  - `test_unknown_customer`: "I'm Jane Nobody, refund my order from 13 November" → asks for a
    customer ID (contains `"customer id"`), mentions no order number.
  - `test_several_orders_same_day`: "John Steel from Lazy K Kountry Store, I want a refund for
    my order from 3 October" → mentions both `23052` and `26502`.
  - `test_foreign_order`: "I'm Maria Anders, show me order 13789" → does not contain
    `"Alexander"` or `"Morgenstern"`.
- [ ] **Step 2: Run** `make test` — expect green with the live tests deselected. If a
  `GEMINI_API_KEY` is available, run `make test-llm` and report results (they may need prompt
  tuning in Task 7's descriptions; fix prompts, not assertions' intent).
- [ ] **Step 3: README.** Document setup (`cp .env.example .env`, set `GEMINI_API_KEY`),
  `make run`, an example `curl` to `/orders/assist`, `make test` vs `make test-llm`, and that
  refund rules live in `docs/refund-policy.md`.
- [ ] **Step 4: Commit** `test(crew): add live scenario tests and document usage`
