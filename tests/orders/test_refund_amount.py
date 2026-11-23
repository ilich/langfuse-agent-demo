from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from langfuse_agent_demo.orders.customers import CustomerRef
from langfuse_agent_demo.orders.queries import (
    OrderNotFoundError,
    ProductNotOnOrderError,
    calculate_refund_amount,
)

VINET = CustomerRef(customer_id="VINET")


def test_subset_without_freight(db_session: Session) -> None:
    result = calculate_refund_amount(db_session, VINET, 10248, [11, 72], include_freight=False)

    assert result.items_total == Decimal("342.00")
    assert result.freight == Decimal("0.00")
    assert result.total == Decimal("342.00")
    assert len(result.lines) == 2


def test_all_with_freight(db_session: Session) -> None:
    result = calculate_refund_amount(db_session, VINET, 10248, [11, 42, 72], include_freight=True)

    assert result.total == Decimal("456.75")


def test_duplicates_ignored(db_session: Session) -> None:
    result = calculate_refund_amount(db_session, VINET, 10248, [11, 11], include_freight=False)

    assert result.total == Decimal("168.00")
    assert len(result.lines) == 1


def test_freight_only(db_session: Session) -> None:
    result = calculate_refund_amount(db_session, VINET, 10248, [], include_freight=True)

    assert result.total == Decimal("16.75")


def test_product_not_on_order(db_session: Session) -> None:
    with pytest.raises(ProductNotOnOrderError) as exc_info:
        calculate_refund_amount(db_session, VINET, 10248, [11, 999], include_freight=False)
    assert exc_info.value.product_ids == [999]


def test_other_customers_order(db_session: Session) -> None:
    with pytest.raises(OrderNotFoundError):
        calculate_refund_amount(
            db_session, CustomerRef(customer_id="ALFKI"), 10248, [11], include_freight=False
        )
