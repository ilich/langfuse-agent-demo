"""CrewAI tools over the order queries. Every tool returns a JSON string.

Known failures come back as ``{"error": "..."}`` so the agent can react (e.g. ask the
customer for their customer ID) instead of the crew failing.

Tools are created per request with :func:`make_order_tools`. The first customer a tool
identifies is locked in for that request: later calls that identify a different customer get
"no customer matches", so one request can never read two customers' orders.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from crewai.tools import BaseTool, tool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import get_settings, get_today
from ..db import get_sessionmaker
from ..orders import queries
from ..orders.customers import CustomerNotFoundError, CustomerRef, resolve_customer

CUSTOMER_NOT_FOUND = (
    "No customer matches the details given. Ask the customer for their customer ID, "
    "or their contact name and company name."
)
INVALID_DATE_RANGE = "date_from must be on or before date_to."
INVALID_DATE = "Dates must be in YYYY-MM-DD format."
POLICY_UNAVAILABLE = "The refund policy is unavailable, so refund eligibility cannot be decided."


@dataclass(frozen=True)
class OrderTools:
    get_order_details: BaseTool
    search_orders: BaseTool
    calculate_refund_amount: BaseTool
    read_refund_policy: BaseTool


class _CustomerLock:
    """Remembers the first customer identified in a request and rejects any other."""

    def __init__(self) -> None:
        self.customer_id: str | None = None

    def resolve(self, session: Session, ref: CustomerRef) -> CustomerRef:
        customer = resolve_customer(session, ref)
        if self.customer_id is None:
            self.customer_id = customer.customer_id
        elif customer.customer_id != self.customer_id:
            raise CustomerNotFoundError
        return CustomerRef(customer_id=customer.customer_id)


def _error(message: str) -> str:
    return json.dumps({"error": message})


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def make_order_tools() -> OrderTools:
    """A fresh set of tools sharing one customer lock; create one set per request."""
    lock = _CustomerLock()

    def run_query(ref: CustomerRef, query: Callable[[Session, CustomerRef], BaseModel]) -> str:
        """Resolve and lock the customer, run the query, and map known failures to errors."""
        try:
            with get_sessionmaker()() as session:
                return query(session, lock.resolve(session, ref)).model_dump_json()
        except CustomerNotFoundError:
            return _error(CUSTOMER_NOT_FOUND)
        except queries.OrderNotFoundError as exc:
            return _error(f"Order {exc.order_id} was not found for this customer.")
        except queries.ProductNotOnOrderError as exc:
            return _error(f"Products {exc.product_ids} are not on order {exc.order_id}.")
        except queries.InvalidDateRangeError:
            return _error(INVALID_DATE_RANGE)

    @tool("get_order_details")
    def get_order_details(
        order_id: int,
        customer_id: str | None = None,
        contact_name: str | None = None,
        company_name: str | None = None,
    ) -> str:
        """Get one order of the identified customer: dates, shipping address, shipper, freight,
        totals and every item (product, category, quantity, unit price, discount as a fraction
        where 0.25 means 25%, discontinued, value). Also returns facts computed as of today:
        shipped, days_since_order, days_since_shipped, shipped_late and days_late. Identify the
        customer with customer_id, or contact_name, or contact_name and company_name, exactly as
        the customer gave them."""
        ref = CustomerRef(
            customer_id=customer_id, contact_name=contact_name, company_name=company_name
        )
        return run_query(ref, lambda s, r: queries.get_order_details(s, r, order_id, get_today()))

    @tool("search_orders")
    def search_orders(
        customer_id: str | None = None,
        contact_name: str | None = None,
        company_name: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> str:
        """List the identified customer's orders, newest first, optionally only those placed
        between date_from and date_to (inclusive, YYYY-MM-DD). Returns at most 50 order
        summaries (order_id, order_date, shipped_date, item_count, order_total), plus
        total_matches and truncated: when truncated is true, more orders exist than were
        returned, so narrow the dates instead of reporting the list as complete. Identify the
        customer with customer_id, or contact_name, or contact_name and company_name."""
        try:
            start, end = _parse_date(date_from), _parse_date(date_to)
        except ValueError:
            return _error(INVALID_DATE)
        ref = CustomerRef(
            customer_id=customer_id, contact_name=contact_name, company_name=company_name
        )
        return run_query(ref, lambda s, r: queries.search_orders(s, r, start, end))

    @tool("calculate_refund_amount")
    def calculate_refund_amount(
        order_id: int,
        refundable_product_ids: list[int],
        include_freight: bool,
        customer_id: str | None = None,
        contact_name: str | None = None,
        company_name: str | None = None,
    ) -> str:
        """Add up the refund for an order: the values of the given refundable products plus the
        freight if include_freight is true. Decide which products and whether freight are
        refundable from the refund policy first; this tool only does the arithmetic. The result
        lists excluded_lines (items not included) and order_item_count: check that every
        excluded item really is non-refundable under the policy. Identify the customer with
        customer_id, or contact_name, or contact_name and company_name."""
        ref = CustomerRef(
            customer_id=customer_id, contact_name=contact_name, company_name=company_name
        )
        return run_query(
            ref,
            lambda s, r: queries.calculate_refund_amount(
                s, r, order_id, refundable_product_ids, include_freight
            ),
        )

    @tool("read_refund_policy")
    def read_refund_policy() -> str:
        """Read the shop's current refund policy (Markdown). Base every refund decision on it."""
        try:
            text = get_settings().refund_policy_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return _error(POLICY_UNAVAILABLE)
        return json.dumps({"policy": text})

    return OrderTools(
        get_order_details=get_order_details,
        search_orders=search_orders,
        calculate_refund_amount=calculate_refund_amount,
        read_refund_policy=read_refund_policy,
    )
