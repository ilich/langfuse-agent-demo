"""CrewAI tools over the order queries. Every tool returns a JSON string.

Known failures come back as ``{"error": "..."}`` so the agent can react (e.g. ask the
customer for their customer ID) instead of the crew failing.
"""

import json
from collections.abc import Callable
from datetime import date

from crewai.tools import tool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import get_settings, get_today
from ..db import get_sessionmaker
from ..orders import queries
from ..orders.customers import CustomerNotFoundError, CustomerRef

CUSTOMER_NOT_FOUND = (
    "No customer matches the details given. Ask the customer for their customer ID, "
    "or their contact name and company name."
)
INVALID_DATE_RANGE = "date_from must be on or before date_to."
INVALID_DATE = "Dates must be in YYYY-MM-DD format."
POLICY_UNAVAILABLE = "The refund policy is unavailable, so refund eligibility cannot be decided."


def _error(message: str) -> str:
    return json.dumps({"error": message})


def _run_query(query: Callable[[Session], BaseModel]) -> str:
    """Run a query in a fresh session and map known failures to error results."""
    try:
        with get_sessionmaker()() as session:
            return query(session).model_dump_json()
    except CustomerNotFoundError:
        return _error(CUSTOMER_NOT_FOUND)
    except queries.OrderNotFoundError as exc:
        return _error(f"Order {exc.order_id} was not found for this customer.")
    except queries.ProductNotOnOrderError as exc:
        return _error(f"Products {exc.product_ids} are not on order {exc.order_id}.")
    except queries.InvalidDateRangeError:
        return _error(INVALID_DATE_RANGE)


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


@tool("get_order_details")
def get_order_details_tool(
    order_id: int,
    customer_id: str | None = None,
    contact_name: str | None = None,
    company_name: str | None = None,
) -> str:
    """Get one order of the identified customer: dates, shipping address, shipper, freight,
    totals and every item (product, category, quantity, unit price, discount, discontinued,
    value). Also returns facts computed as of today: shipped, days_since_order,
    days_since_shipped, shipped_late and days_late. Identify the customer with customer_id,
    or contact_name, or contact_name and company_name, exactly as the customer gave them."""
    ref = CustomerRef(customer_id=customer_id, contact_name=contact_name, company_name=company_name)
    return _run_query(lambda s: queries.get_order_details(s, ref, order_id, get_today()))


@tool("search_orders")
def search_orders_tool(
    customer_id: str | None = None,
    contact_name: str | None = None,
    company_name: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> str:
    """List the identified customer's orders, newest first, optionally only those placed
    between date_from and date_to (inclusive, YYYY-MM-DD). Returns total_matches and order
    summaries (order_id, order_date, shipped_date, item_count, order_total). Identify the
    customer with customer_id, or contact_name, or contact_name and company_name."""
    try:
        start, end = _parse_date(date_from), _parse_date(date_to)
    except ValueError:
        return _error(INVALID_DATE)
    ref = CustomerRef(customer_id=customer_id, contact_name=contact_name, company_name=company_name)
    return _run_query(lambda s: queries.search_orders(s, ref, start, end))


@tool("calculate_refund_amount")
def calculate_refund_amount_tool(
    order_id: int,
    refundable_product_ids: list[int],
    include_freight: bool,
    customer_id: str | None = None,
    contact_name: str | None = None,
    company_name: str | None = None,
) -> str:
    """Add up the refund for an order: the values of the given refundable products plus the
    freight if include_freight is true. Decide which products and whether freight are
    refundable from the refund policy first; this tool only does the arithmetic. Identify the
    customer with customer_id, or contact_name, or contact_name and company_name."""
    ref = CustomerRef(customer_id=customer_id, contact_name=contact_name, company_name=company_name)
    return _run_query(
        lambda s: queries.calculate_refund_amount(
            s, ref, order_id, refundable_product_ids, include_freight
        )
    )


@tool("read_refund_policy")
def read_refund_policy_tool() -> str:
    """Read the shop's current refund policy (Markdown). Base every refund decision on it."""
    try:
        text = get_settings().refund_policy_path.read_text(encoding="utf-8")
    except OSError:
        return _error(POLICY_UNAVAILABLE)
    return json.dumps({"policy": text})
