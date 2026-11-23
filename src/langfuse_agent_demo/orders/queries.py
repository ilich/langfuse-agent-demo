"""Read-only order queries scoped to one identified customer."""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import Order, OrderDetail, Product
from .customers import CustomerRef, resolve_customer
from .schemas import OrderDetails, OrderItem

CENT = Decimal("0.01")


class OrderNotFoundError(Exception):
    """The order does not exist or belongs to another customer (deliberately indistinguishable)."""

    def __init__(self, order_id: int) -> None:
        super().__init__(f"Order {order_id} not found")
        self.order_id = order_id


def item_value(unit_price: Decimal, quantity: int, discount: float) -> Decimal:
    """unit price x quantity x (1 - discount), rounded half-up to cents."""
    value = unit_price * quantity * (1 - Decimal(str(discount)))
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _day(value: datetime | None) -> date | None:
    return value.date() if value is not None else None


def _money(value: Decimal | None) -> Decimal:
    return (value or Decimal(0)).quantize(CENT, rounding=ROUND_HALF_UP)


def _load_order(session: Session, ref: CustomerRef, order_id: int) -> Order:
    customer = resolve_customer(session, ref)
    order = session.scalars(
        select(Order)
        .where(Order.order_id == order_id, Order.customer_id == customer.customer_id)
        .options(
            selectinload(Order.order_details)
            .selectinload(OrderDetail.product)
            .selectinload(Product.category),
            selectinload(Order.shipper),
            selectinload(Order.customer),
        )
    ).one_or_none()
    if order is None:
        raise OrderNotFoundError(order_id)
    return order


def get_order_details(
    session: Session, ref: CustomerRef, order_id: int, today: date
) -> OrderDetails:
    order = _load_order(session, ref, order_id)

    items = [
        OrderItem(
            product_id=line.product_id,
            product_name=line.product.product_name,
            category=line.product.category.category_name if line.product.category else None,
            quantity=line.quantity,
            unit_price=_money(line.unit_price),
            discount=line.discount,
            discontinued=line.product.discontinued,
            value=item_value(line.unit_price, line.quantity, line.discount),
        )
        for line in order.order_details
    ]
    order_date = _day(order.order_date)
    required = _day(order.required_date)
    shipped = _day(order.shipped_date)
    items_total = sum((i.value for i in items), Decimal("0.00"))
    freight = _money(order.freight)

    return OrderDetails(
        order_id=order.order_id,
        customer_id=order.customer_id or "",
        company_name=order.customer.company_name if order.customer else None,
        order_date=order_date,
        required_date=required,
        shipped_date=shipped,
        shipped=shipped is not None,
        days_since_order=(today - order_date).days if order_date else None,
        days_since_shipped=(today - shipped).days if shipped else None,
        shipped_late=(shipped > required) if shipped and required else None,
        days_late=max(0, (shipped - required).days) if shipped and required else None,
        shipper=order.shipper.company_name if order.shipper else None,
        ship_name=order.ship_name,
        ship_address=order.ship_address,
        ship_city=order.ship_city,
        ship_region=order.ship_region,
        ship_postal_code=order.ship_postal_code,
        ship_country=order.ship_country,
        freight=freight,
        items_total=items_total,
        order_total=items_total + freight,
        items=items,
    )
