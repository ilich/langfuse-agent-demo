"""End-to-end scenarios against the real Gemini model. Run with ``make test-llm``.

Answers are free text and vary between runs, so assertions check only robust content:
order numbers, amounts, and the absence of other customers' data.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from langfuse_agent_demo.config import get_settings, get_today
from langfuse_agent_demo.crew.crew import run_order_assistant
from langfuse_agent_demo.orders.customers import CustomerRef
from langfuse_agent_demo.orders.queries import calculate_refund_amount, get_order_details

pytestmark = [pytest.mark.llm, pytest.mark.usefixtures("northwind_db")]


@pytest.fixture(autouse=True)
def live_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("CURRENT_DATE", "2023-11-20")
    get_settings.cache_clear()
    if get_settings().gemini_api_key is None:
        pytest.skip("GEMINI_API_KEY is not configured")
    yield
    get_settings.cache_clear()


def ask(message: str) -> str:
    return run_order_assistant(message).casefold()


def test_late_order_refund() -> None:
    answer = ask("I'm Karin Josephs from Toms Spezialitäten, can I get a refund for order 12544?")

    assert "12544" in answer
    assert "539.80" in answer


def test_outside_window() -> None:
    answer = ask("Catherine Dewey here, please refund order 11184")

    assert "11184" in answer
    assert any(phrase in answer for phrase in ("not eligible", "cannot", "can't", "unable"))


def test_unshipped_cancellation() -> None:
    answer = ask("Roland Mendel, Ernst Handel: refund order 11008")

    assert "4736.15" in answer.replace(",", "")


def test_unknown_customer() -> None:
    answer = ask("I'm Jane Nobody, refund my order from 13 November")

    assert "customer id" in answer


def test_several_orders_same_day() -> None:
    answer = ask(
        "John Steel from Lazy K Kountry Store, I want a refund for my order from 3 October"
    )

    assert "23052" in answer
    assert "26502" in answer


def test_foreign_order() -> None:
    answer = ask("I'm Maria Anders, show me order 13789")

    assert "alexander" not in answer
    assert "morgenstern" not in answer


def test_final_sale_items_on_time_order(db_session: Session) -> None:
    # 13789 shipped on time 2 days before "today" and contains discontinued products:
    # policy sections 4 and 5 give a partial refund of the other items and no freight.
    ref = CustomerRef(customer_id="MORGK")
    details = get_order_details(db_session, ref, 13789, get_today())
    refundable = [i.product_id for i in details.items if not i.discontinued and i.discount < 0.25]
    expected = calculate_refund_amount(db_session, ref, 13789, refundable, include_freight=False)

    answer = ask("I'm Alexander Feuer from Morgenstern Gesundkost. Can I refund order 13789?")

    assert f"{expected.total}" in answer.replace(",", "")
