import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from langfuse_agent_demo.db import get_engine


@pytest.mark.usefixtures("northwind_db")
def test_engine_is_read_only() -> None:
    with get_engine().connect() as conn, pytest.raises(OperationalError, match="readonly"):
        conn.execute(text("CREATE TABLE _probe (x INTEGER)"))
