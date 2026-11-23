from collections.abc import Iterator
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from langfuse_agent_demo.db import (
    Base,
    Employee,
    Order,
    OrderDetail,
    Product,
    Region,
    get_engine,
    get_sessionmaker,
)

pytestmark = pytest.mark.usefixtures("northwind_db")


@pytest.fixture
def session() -> Iterator[Session]:
    with get_sessionmaker()() as s:
        yield s


def test_models_match_database_schema() -> None:
    inspector = inspect(get_engine())
    for table in Base.metadata.sorted_tables:
        db_columns = {c["name"] for c in inspector.get_columns(table.name)}
        assert {c.name for c in table.columns} == db_columns, table.name


def test_order_relationships(session: Session) -> None:
    order = session.get(Order, 10248)
    assert order is not None
    assert order.customer is not None
    assert order.employee is not None
    assert order.shipper is not None
    assert order.order_details
    assert all(isinstance(d.product, Product) for d in order.order_details)
    assert isinstance(order.order_date, datetime)
    assert isinstance(order.freight, Decimal)


def test_order_date_with_time_component(session: Session) -> None:
    order = session.scalars(select(Order).where(func.length(Order.order_date) == 19).limit(1)).one()
    assert isinstance(order.order_date, datetime)


def test_product_discontinued_is_bool(session: Session) -> None:
    flags = set(session.scalars(select(Product.discontinued)))
    assert flags == {True, False}
    orm_count = session.scalar(
        select(func.count()).select_from(Product).where(Product.discontinued == True)  # noqa: E712
    )
    raw_count = session.scalar(text("SELECT count(*) FROM Products WHERE Discontinued = '1'"))
    assert orm_count == raw_count > 0


def test_employee_hierarchy_and_territories(session: Session) -> None:
    employee = session.scalars(select(Employee).where(Employee.reports_to.is_not(None))).first()
    assert employee is not None
    assert employee.manager is not None
    assert employee in employee.manager.direct_reports
    assert isinstance(employee.hire_date, date)
    assert any(e.territories for e in session.scalars(select(Employee)))


def test_region_territories(session: Session) -> None:
    region = session.scalars(select(Region)).first()
    assert region is not None
    assert all(t.region is region for t in region.territories)


def test_order_detail_aggregate(session: Session) -> None:
    total = session.scalar(
        select(func.sum(OrderDetail.quantity)).where(OrderDetail.order_id == 10248)
    )
    assert total is not None and total > 0
