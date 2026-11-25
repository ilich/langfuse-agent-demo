import pytest
from sqlalchemy.orm import Session

from langfuse_agent_demo.orders.customers import (
    CustomerNotFoundError,
    CustomerRef,
    resolve_customer,
)


def test_by_customer_id(db_session: Session) -> None:
    assert resolve_customer(db_session, CustomerRef(customer_id="ALFKI")).customer_id == "ALFKI"


def test_by_contact_name(db_session: Session) -> None:
    ref = CustomerRef(contact_name="Maria Anders")
    assert resolve_customer(db_session, ref).customer_id == "ALFKI"


def test_by_contact_and_company(db_session: Session) -> None:
    ref = CustomerRef(contact_name="Maria Anders", company_name="Alfreds Futterkiste")
    assert resolve_customer(db_session, ref).customer_id == "ALFKI"


def test_case_whitespace_and_accents(db_session: Session) -> None:
    ref = CustomerRef(contact_name="  ANTONIO MORENO ", company_name="antonio moreno taquería")
    assert resolve_customer(db_session, ref).customer_id == "ANTON"
    assert resolve_customer(db_session, CustomerRef(customer_id=" alfki ")).customer_id == "ALFKI"


def test_stored_id_with_trailing_space(db_session: Session) -> None:
    assert resolve_customer(db_session, CustomerRef(customer_id="Val2")).customer_id == "Val2 "


def test_company_alone_rejected(db_session: Session) -> None:
    with pytest.raises(CustomerNotFoundError):
        resolve_customer(db_session, CustomerRef(company_name="Alfreds Futterkiste"))


@pytest.mark.parametrize(
    "ref",
    [
        CustomerRef(contact_name="Maria Anders", company_name="Hanari Carnes"),
        CustomerRef(customer_id="ALFKI", contact_name="Paul Henriot"),
    ],
)
def test_mismatched_identifiers_rejected(db_session: Session, ref: CustomerRef) -> None:
    with pytest.raises(CustomerNotFoundError):
        resolve_customer(db_session, ref)


@pytest.mark.parametrize(
    "ref",
    [CustomerRef(contact_name="Nobody Here"), CustomerRef(), CustomerRef(customer_id="   ")],
)
def test_unknown_and_empty(db_session: Session, ref: CustomerRef) -> None:
    with pytest.raises(CustomerNotFoundError):
        resolve_customer(db_session, ref)
