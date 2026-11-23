"""Result models returned by the order queries (and serialised by the agent tools)."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class OrderItem(BaseModel):
    product_id: int
    product_name: str
    category: str | None
    quantity: int
    unit_price: Decimal
    discount: float
    discontinued: bool
    # unit_price x quantity x (1 - discount), rounded to cents.
    value: Decimal


class OrderDetails(BaseModel):
    order_id: int
    customer_id: str
    company_name: str | None
    order_date: date | None
    required_date: date | None
    shipped_date: date | None
    shipped: bool
    # Facts computed as of "today", so agents never do date arithmetic.
    days_since_order: int | None
    days_since_shipped: int | None
    shipped_late: bool | None
    days_late: int | None
    shipper: str | None
    ship_name: str | None
    ship_address: str | None
    ship_city: str | None
    ship_region: str | None
    ship_postal_code: str | None
    ship_country: str | None
    freight: Decimal
    items_total: Decimal
    order_total: Decimal
    items: list[OrderItem]
