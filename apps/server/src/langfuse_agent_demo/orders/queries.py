"""Read-only order queries scoped to one identified customer."""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session, selectinload

from ..db import Order, OrderDetail, Product
from .customers import CustomerRef, resolve_customer
from .schemas import (
    OrderDetails,
    OrderItem,
    OrderSearchResult,
    OrderSummary,
    RefundCalculation,
    RefundLine,
)

CENT = Decimal("0.01")


class OrderNotFoundError(Exception):
    """The order does not exist or belongs to another customer (deliberately indistinguishable)."""

    def __init__(self, order_id: int) -> None:
        super().__init__(f"Order {order_id} not found")
        self.order_id = order_id


class ProductNotOnOrderError(Exception):
    """Some requested products are not on the order."""

    def __init__(self, order_id: int, product_ids: list[int]) -> None:
        super().__init__(f"Products {product_ids} are not on order {order_id}")
        self.order_id = order_id
        self.product_ids = product_ids


class InvalidDateRangeError(ValueError):
    """``date_from`` is after ``date_to``."""


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


def search_orders(
    session: Session,
    ref: CustomerRef,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
) -> OrderSearchResult:
    """The customer's orders placed between the dates (inclusive, date part only), newest first."""
    if date_from and date_to and date_from > date_to:
        raise InvalidDateRangeError("date_from must be on or before date_to")
    customer = resolve_customer(session, ref)

    # Compare on the date part: stored values may or may not include a time.
    order_day = func.date(Order.order_date)
    conditions: list[ColumnElement[bool]] = [Order.customer_id == customer.customer_id]
    if date_from:
        conditions.append(order_day >= date_from.isoformat())
    if date_to:
        conditions.append(order_day <= date_to.isoformat())

    total = session.scalar(select(func.count()).select_from(Order).where(*conditions)) or 0
    orders = session.scalars(
        select(Order)
        .where(*conditions)
        .order_by(Order.order_date.desc(), Order.order_id.desc())
        .limit(limit)
        .options(selectinload(Order.order_details))
    ).all()

    return OrderSearchResult(
        customer_id=customer.customer_id,
        total_matches=total,
        truncated=total > len(orders),
        orders=[
            OrderSummary(
                order_id=order.order_id,
                order_date=_day(order.order_date),
                shipped_date=_day(order.shipped_date),
                item_count=len(order.order_details),
                order_total=sum(
                    (item_value(d.unit_price, d.quantity, d.discount) for d in order.order_details),
                    Decimal("0.00"),
                )
                + _money(order.freight),
            )
            for order in orders
        ],
    )


def calculate_refund_amount(
    session: Session,
    ref: CustomerRef,
    order_id: int,
    refundable_product_ids: list[int],
    include_freight: bool,
) -> RefundCalculation:
    """Add up the chosen items (and freight). Which ones are refundable is decided elsewhere."""
    # today only affects day counts, which are not used here.
    details = get_order_details(session, ref, order_id, date.today())
    by_product = {item.product_id: item for item in details.items}
    wanted = list(dict.fromkeys(refundable_product_ids))
    missing = [product_id for product_id in wanted if product_id not in by_product]
    if missing:
        raise ProductNotOnOrderError(order_id, missing)

    lines = [
        RefundLine(
            product_id=product_id,
            product_name=by_product[product_id].product_name,
            value=by_product[product_id].value,
        )
        for product_id in wanted
    ]
    excluded = [
        RefundLine(product_id=item.product_id, product_name=item.product_name, value=item.value)
        for item in details.items
        if item.product_id not in wanted
    ]
    items_total = sum((line.value for line in lines), Decimal("0.00"))
    freight = details.freight if include_freight else Decimal("0.00")
    return RefundCalculation(
        order_id=order_id,
        lines=lines,
        excluded_lines=excluded,
        order_item_count=len(details.items),
        freight_available=details.freight,
        items_total=items_total,
        freight=freight,
        total=items_total + freight,
    )
