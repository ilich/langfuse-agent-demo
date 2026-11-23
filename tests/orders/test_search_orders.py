from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from langfuse_agent_demo.orders.customers import CustomerNotFoundError, CustomerRef
from langfuse_agent_demo.orders.queries import InvalidDateRangeError, search_orders


def test_search_by_date_range(db_session: Session) -> None:
    result = search_orders(
        db_session, CustomerRef(customer_id="VINET"), date(2016, 7, 1), date(2016, 7, 31)
    )

    assert result.customer_id == "VINET"
    assert result.total_matches == 2
    assert {o.order_id for o in result.orders} == {10248, 16165}
    dates = [o.order_date for o in result.orders]
    assert dates == sorted(dates, key=lambda d: d or date.min, reverse=True)
    order = next(o for o in result.orders if o.order_id == 10248)
    assert order.order_total == Decimal("456.75")
    assert order.item_count == 3


def test_single_day_inclusive_with_time_parts(db_session: Session) -> None:
    day = date(2023, 10, 3)
    result = search_orders(db_session, CustomerRef(customer_id="LAZYK"), day, day)

    assert {o.order_id for o in result.orders} == {23052, 26502}


def test_no_range_and_limit(db_session: Session) -> None:
    result = search_orders(db_session, CustomerRef(customer_id="VINET"), limit=5)

    assert result.total_matches == 158
    assert len(result.orders) == 5
    dates = [o.order_date or date.min for o in result.orders]
    assert dates == sorted(dates, reverse=True)


def test_inverted_range(db_session: Session) -> None:
    with pytest.raises(InvalidDateRangeError):
        search_orders(
            db_session, CustomerRef(customer_id="VINET"), date(2023, 1, 2), date(2023, 1, 1)
        )


def test_unknown_customer(db_session: Session) -> None:
    with pytest.raises(CustomerNotFoundError):
        search_orders(db_session, CustomerRef(contact_name="Nobody Here"))
