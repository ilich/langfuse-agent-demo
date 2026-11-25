"""Identify a customer from the details they give: customer ID, contact name, company name."""

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Customer


class CustomerRef(BaseModel):
    customer_id: str | None = None
    contact_name: str | None = None
    company_name: str | None = None


class CustomerNotFoundError(Exception):
    """No single customer matches every identifier given."""


def _normalise(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().casefold() or None


def resolve_customer(session: Session, ref: CustomerRef) -> Customer:
    """Return the one customer matching every identifier in ``ref``.

    Accepted: customer ID, contact name, or contact name + company name (company name alone is
    not unique). Matching is exact after trimming and case-folding; it is done in Python
    because SQLite's ``lower()`` only folds ASCII.
    """
    wanted = {
        "customer_id": _normalise(ref.customer_id),
        "contact_name": _normalise(ref.contact_name),
        "company_name": _normalise(ref.company_name),
    }
    if wanted["customer_id"] is None and wanted["contact_name"] is None:
        raise CustomerNotFoundError

    given = {field: value for field, value in wanted.items() if value is not None}
    matches = [
        customer
        for customer in session.scalars(select(Customer))
        if all(_normalise(getattr(customer, field)) == value for field, value in given.items())
    ]
    if len(matches) != 1:
        raise CustomerNotFoundError
    return matches[0]
