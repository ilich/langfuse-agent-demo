from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from langfuse_agent_demo.main import app
from langfuse_agent_demo.routers.orders import get_assistant

client = TestClient(app)


@pytest.fixture
def use_assistant() -> Iterator[Callable[[Callable[[str], str]], None]]:
    def install(assistant: Callable[[str], str]) -> None:
        app.dependency_overrides[get_assistant] = lambda: assistant

    yield install
    app.dependency_overrides.clear()


def test_assist_returns_answer(use_assistant: Callable[[Callable[[str], str]], None]) -> None:
    received: list[str] = []

    def assistant(message: str) -> str:
        received.append(message)
        return "ok"

    use_assistant(assistant)
    response = client.post("/orders/assist", json={"message": "Where is order 10248?"})

    assert response.status_code == 200
    assert response.json() == {"answer": "ok"}
    assert received == ["Where is order 10248?"]


def test_assist_failure_is_503(use_assistant: Callable[[Callable[[str], str]], None]) -> None:
    def assistant(message: str) -> str:
        raise RuntimeError("boom")

    use_assistant(assistant)
    response = client.post("/orders/assist", json={"message": "Refund order 10248"})

    assert response.status_code == 503
    assert response.json() == {
        "error": "The order assistant is unavailable. Please try again later."
    }
    assert "boom" not in response.text


def test_assist_rejects_empty_message() -> None:
    response = client.post("/orders/assist", json={"message": "   "})

    assert response.status_code == 422
