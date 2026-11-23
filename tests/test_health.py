from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine

from langfuse_agent_demo.db import get_engine
from langfuse_agent_demo.main import app

client = TestClient(app)


@pytest.fixture
def override_engine() -> Iterator[list[Engine]]:
    engines: list[Engine] = []
    app.dependency_overrides[get_engine] = lambda: engines[0]
    yield engines
    app.dependency_overrides.clear()
    for engine in engines:
        engine.dispose()


@pytest.mark.usefixtures("northwind_db")
def test_health_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"success": True}


def test_health_missing_database(tmp_path: Path, override_engine: list[Engine]) -> None:
    missing = tmp_path / "missing.db"
    override_engine.append(create_engine(f"sqlite:///file:{missing}?mode=rw&uri=true"))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"success": False, "error": "Database is not accessible"}
    assert not missing.exists()


def test_health_database_without_northwind_tables(
    tmp_path: Path, override_engine: list[Engine]
) -> None:
    override_engine.append(create_engine(f"sqlite:///{tmp_path / 'empty.db'}"))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"success": False, "error": "Database is not accessible"}
