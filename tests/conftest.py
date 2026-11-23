from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from langfuse_agent_demo.db.session import get_db_path, get_sessionmaker


@pytest.fixture
def northwind_db() -> Path:
    """Path to the configured Northwind database; skips the test if it is unavailable."""
    try:
        path = get_db_path()
    except ValidationError:
        pytest.skip("NORTHWIND_DB_PATH is not set (copy .env.example to .env)")
    if not path.exists():
        pytest.skip(f"Northwind database not found at {path}")
    return path


@pytest.fixture
def db_session(northwind_db: Path) -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session
