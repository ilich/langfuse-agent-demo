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
)

pytestmark = pytest.mark.usefixtures("northwind_db")


def test_models_match_database_schema() -> None:
    inspector = inspect(get_engine())
    for table in Base.metadata.sorted_tables:
        db_columns = {c["name"] for c in inspector.get_columns(table.name)}
        assert {c.name for c in table.columns} == db_columns, table.name


def test_order_relationships(db_session: Session) -> None:
    order = db_session.get(Order, 10248)
    assert order is not None
    assert order.customer is not None
    assert order.employee is not None
    assert order.shipper is not None
    assert order.order_details
    assert all(isinstance(d.product, Product) for d in order.order_details)
    assert isinstance(order.order_date, datetime)
    assert isinstance(order.freight, Decimal)


def test_order_date_with_time_component(db_session: Session) -> None:
    order = db_session.scalars(
        select(Order).where(func.length(Order.order_date) == 19).limit(1)
    ).one()
    assert isinstance(order.order_date, datetime)


def test_product_discontinued_is_bool(db_session: Session) -> None:
    flags = set(db_session.scalars(select(Product.discontinued)))
    assert flags == {True, False}
    orm_count = db_session.scalar(
        select(func.count()).select_from(Product).where(Product.discontinued == True)  # noqa: E712
    )
    raw_count = db_session.scalar(text("SELECT count(*) FROM Products WHERE Discontinued = '1'"))
    assert orm_count == raw_count > 0


def test_employee_hierarchy_and_territories(db_session: Session) -> None:
    employee = db_session.scalars(select(Employee).where(Employee.reports_to.is_not(None))).first()
    assert employee is not None
    assert employee.manager is not None
    assert employee in employee.manager.direct_reports
    assert isinstance(employee.hire_date, date)
    assert any(e.territories for e in db_session.scalars(select(Employee)))


def test_region_territories(db_session: Session) -> None:
    region = db_session.scalars(select(Region)).first()
    assert region is not None
    assert all(t.region is region for t in region.territories)


def test_order_detail_aggregate(db_session: Session) -> None:
    total = db_session.scalar(
        select(func.sum(OrderDetail.quantity)).where(OrderDetail.order_id == 10248)
    )
    assert total is not None and total > 0
