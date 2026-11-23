from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from langfuse_agent_demo.orders.customers import CustomerNotFoundError, CustomerRef
from langfuse_agent_demo.orders.queries import OrderNotFoundError, get_order_details

TODAY = date(2023, 11, 20)


def test_details_items_and_totals(db_session: Session) -> None:
    details = get_order_details(db_session, CustomerRef(customer_id="VINET"), 10248, TODAY)

    assert len(details.items) == 3
    item = next(i for i in details.items if i.product_id == 42)
    assert item.product_name == "Singaporean Hokkien Fried Mee"
    assert item.discontinued is True
    assert item.category == "Grains/Cereals"
    assert item.value == Decimal("98.00")
    assert details.items_total == Decimal("440.00")
    assert details.freight == Decimal("16.75")
    assert details.order_total == Decimal("456.75")
    assert details.shipped is True
    assert details.shipped_late is False
    assert details.days_late == 0
    assert details.days_since_shipped == (TODAY - date(2016, 7, 16)).days
    assert details.ship_city == "Reims"
    assert details.shipper is not None


def test_discounted_item_value(db_session: Session) -> None:
    details = get_order_details(db_session, CustomerRef(customer_id="HANAR"), 10250, TODAY)

    item = next(i for i in details.items if i.product_id == 51)
    assert item.value == Decimal("1261.40")
    assert item.discount == 0.15
    assert details.items_total == Decimal("1552.60")


def test_late_shipment_with_time_parts(db_session: Session) -> None:
    ref = CustomerRef(contact_name="Karin Josephs")
    details = get_order_details(db_session, ref, 12544, TODAY)

    assert details.shipped_late is True
    assert details.days_late == 6
    assert details.days_since_shipped == 19
    assert details.days_since_order == 42
    assert details.shipped_date == date(2023, 11, 1)


def test_unshipped_order(db_session: Session) -> None:
    details = get_order_details(db_session, CustomerRef(customer_id="ERNSH"), 11008, TODAY)

    assert details.shipped is False
    assert details.shipped_date is None
    assert details.days_since_shipped is None
    assert details.shipped_late is None
    assert details.days_late is None


@pytest.mark.parametrize("order_id", [10248, 99999999])
def test_other_customers_order_not_found(db_session: Session, order_id: int) -> None:
    with pytest.raises(OrderNotFoundError) as exc_info:
        get_order_details(db_session, CustomerRef(customer_id="ALFKI"), order_id, TODAY)
    assert exc_info.value.order_id == order_id


def test_unknown_customer(db_session: Session) -> None:
    with pytest.raises(CustomerNotFoundError):
        get_order_details(db_session, CustomerRef(contact_name="Nobody Here"), 10248, TODAY)
