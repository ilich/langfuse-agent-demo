import re
from collections.abc import Iterator, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from langfuse import Langfuse
from langfuse.api import NotFoundError

from langfuse_agent_demo.config import get_settings
from langfuse_agent_demo.crew.prompts import (
    PROMPT_NAMES,
    TASK_VARIABLES,
    PromptsUnavailableError,
    fetch_prompts,
    langfuse_client,
    load_prompt_file,
    to_crewai,
)

TASK_PROMPT = "order-assistant/resolve-request"


class FakeLangfuse:
    """Stands in for the Langfuse client's get_prompt; records each call's keyword arguments."""

    def __init__(
        self, prompts: Mapping[str, tuple[str, int]], error: Exception | None = None
    ) -> None:
        self.prompts = prompts
        self.error = error
        self.call_kwargs: list[dict[str, Any]] = []

    def get_prompt(self, name: str, **kwargs: Any) -> SimpleNamespace:
        self.call_kwargs.append(kwargs)
        if self.error is not None:
            raise self.error
        text, version = self.prompts[name]
        return SimpleNamespace(name=name, prompt=text, version=version)


def fetch(prompts: Mapping[str, str], version: int = 1) -> Any:
    client = FakeLangfuse({name: (text, version) for name, text in prompts.items()})
    return fetch_prompts(cast(Langfuse, client))


def test_file_has_exactly_the_crew_prompts() -> None:
    assert set(load_prompt_file()) == set(PROMPT_NAMES)
    assert len(PROMPT_NAMES) == 11


def test_only_the_task_prompt_uses_variables() -> None:
    texts = load_prompt_file()
    assert set(re.findall(r"\{\{\s*(\w+)\s*\}\}", texts[TASK_PROMPT])) == TASK_VARIABLES
    others = [text for name, text in texts.items() if name != TASK_PROMPT]
    assert not any("{" in text or "}" in text for text in others)


def test_to_crewai() -> None:
    assert to_crewai("Hi {{message}} on {{ today }}") == "Hi {message} on {today}"


def test_fetch_converts_and_records_versions() -> None:
    client = FakeLangfuse({name: (text, 3) for name, text in load_prompt_file().items()})

    prompts = fetch_prompts(cast(Langfuse, client))

    assert "{message}" in prompts[TASK_PROMPT]
    assert "{{" not in prompts[TASK_PROMPT]
    assert prompts.versions["order-assistant/refund-agent/goal"] == 3
    assert len(client.call_kwargs) == 11
    assert all(
        kwargs
        == {
            "label": "production",
            "type": "text",
            "cache_ttl_seconds": 60,
            "max_retries": 1,
            "fetch_timeout_seconds": 5,
        }
        for kwargs in client.call_kwargs
    )


def test_missing_prompt_points_at_push() -> None:
    client = FakeLangfuse({}, error=NotFoundError(body={"message": "Prompt not found"}))

    with pytest.raises(PromptsUnavailableError, match=f"{TASK_PROMPT}.*make prompts-push"):
        fetch_prompts(cast(Langfuse, client))


def test_unreachable_langfuse_points_at_settings() -> None:
    # A wrong region or rotated keys is not fixed by pushing prompts.
    client = FakeLangfuse({}, error=ConnectionError("down"))

    with pytest.raises(PromptsUnavailableError, match=TASK_PROMPT) as raised:
        fetch_prompts(cast(Langfuse, client))

    assert "make prompts-push" not in str(raised.value)
    assert "LANGFUSE_BASE_URL" in str(raised.value)
    assert "down" in str(raised.value)


def test_unknown_variable_rejected() -> None:
    texts = load_prompt_file() | {"order-assistant/search-agent/goal": "Find {{customer}}"}

    with pytest.raises(PromptsUnavailableError, match="order-assistant/search-agent/goal"):
        fetch(texts)


def test_unknown_task_variable_rejected() -> None:
    texts = load_prompt_file() | {TASK_PROMPT: "{{message}} for {{customer}}"}

    with pytest.raises(PromptsUnavailableError, match=TASK_PROMPT):
        fetch(texts)


@pytest.mark.parametrize("variable", sorted(TASK_VARIABLES))
def test_task_prompt_missing_variable_rejected(variable: str) -> None:
    # Without {{message}} the crew would never see the customer's text, yet answer 200.
    texts = load_prompt_file()
    edited = texts[TASK_PROMPT].replace("{{" + variable + "}}", "")

    with pytest.raises(PromptsUnavailableError, match=f"{TASK_PROMPT}.*{variable}"):
        fetch(texts | {TASK_PROMPT: edited})


def test_stray_brace_rejected() -> None:
    # CrewAI would fail mid-run interpolating a single brace.
    texts = load_prompt_file() | {"order-assistant/expected-answer": "Reply as JSON {answer}"}

    with pytest.raises(PromptsUnavailableError, match="order-assistant/expected-answer"):
        fetch(texts)


@pytest.fixture
def no_langfuse_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.chdir(tmp_path)  # ignore the developer's .env
    monkeypatch.setenv("NORTHWIND_DB_PATH", str(tmp_path / "northwind.db"))
    for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.usefixtures("no_langfuse_keys")
def test_client_requires_keys() -> None:
    with pytest.raises(PromptsUnavailableError, match="LANGFUSE_PUBLIC_KEY"):
        langfuse_client()
