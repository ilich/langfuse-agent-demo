import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from langfuse_agent_demo.config import get_settings
from langfuse_agent_demo.crew.tools import (
    calculate_refund_amount_tool,
    get_order_details_tool,
    read_refund_policy_tool,
    search_orders_tool,
)

CUSTOMER_NOT_FOUND = (
    "No customer matches the details given. Ask the customer for their customer ID, "
    "or their contact name and company name."
)

pytestmark = pytest.mark.usefixtures("northwind_db")


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("CURRENT_DATE", "2023-11-20")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def run(tool: Any, **kwargs: Any) -> Any:
    return json.loads(tool.run(**kwargs))


def test_get_order_details_tool() -> None:
    result = run(get_order_details_tool, contact_name="Karin Josephs", order_id=12544)

    assert result["days_late"] == 6
    assert result["days_since_shipped"] == 19


def test_not_found_is_identical_for_foreign_and_missing_orders() -> None:
    foreign = run(get_order_details_tool, customer_id="ALFKI", order_id=10248)
    missing = run(get_order_details_tool, customer_id="ALFKI", order_id=99999999)

    assert foreign == {"error": "Order 10248 was not found for this customer."}
    assert missing == {"error": "Order 99999999 was not found for this customer."}


def test_unknown_customer_tool() -> None:
    result = run(get_order_details_tool, contact_name="Nobody Here", order_id=10248)

    assert result == {"error": CUSTOMER_NOT_FOUND}


def test_search_tool_dates_and_errors() -> None:
    found = run(
        search_orders_tool, customer_id="VINET", date_from="2016-07-01", date_to="2016-07-31"
    )
    inverted = run(
        search_orders_tool, customer_id="VINET", date_from="2023-01-02", date_to="2023-01-01"
    )
    bad = run(search_orders_tool, customer_id="VINET", date_from="13 November")

    assert found["total_matches"] == 2
    assert inverted == {"error": "date_from must be on or before date_to."}
    assert bad == {"error": "Dates must be in YYYY-MM-DD format."}


def test_refund_tool() -> None:
    ok = run(
        calculate_refund_amount_tool,
        customer_id="VINET",
        order_id=10248,
        refundable_product_ids=[11, 72],
        include_freight=False,
    )
    bad = run(
        calculate_refund_amount_tool,
        customer_id="VINET",
        order_id=10248,
        refundable_product_ids=[999],
        include_freight=False,
    )

    assert ok["total"] == "342.00"
    assert bad == {"error": "Products [999] are not on order 10248."}


def test_read_refund_policy_reads_file_each_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy = tmp_path / "policy.md"
    policy.write_text("Version 1", encoding="utf-8")
    monkeypatch.setenv("REFUND_POLICY_PATH", str(policy))
    get_settings.cache_clear()

    first = run(read_refund_policy_tool)
    policy.write_text("Version 2", encoding="utf-8")
    second = run(read_refund_policy_tool)

    assert first == {"policy": "Version 1"}
    assert second == {"policy": "Version 2"}


def test_read_refund_policy_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REFUND_POLICY_PATH", str(tmp_path / "missing.md"))
    get_settings.cache_clear()

    result = run(read_refund_policy_tool)

    assert result == {
        "error": "The refund policy is unavailable, so refund eligibility cannot be decided."
    }
