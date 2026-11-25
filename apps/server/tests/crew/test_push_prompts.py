from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any, cast

import pytest
from langfuse import Langfuse
from langfuse.api import NotFoundError

from langfuse_agent_demo.crew import push_prompts as push_module
from langfuse_agent_demo.crew.prompts import PromptsUnavailableError, load_prompt_file
from langfuse_agent_demo.crew.push_prompts import main, push_prompts

TEXTS = load_prompt_file()
NAME = "order-assistant/resolve-request"


class FakeLangfuse:
    """In-memory prompt store: production text per name; records create_prompt calls."""

    def __init__(
        self, existing: Mapping[str, str] | None = None, error: Exception | None = None
    ) -> None:
        self.prompts = dict(existing or {})
        self.error = error
        self.created: list[dict[str, Any]] = []
        self.flushed = False

    def get_prompt(self, name: str, **kwargs: Any) -> SimpleNamespace:
        if self.error is not None:
            raise self.error
        if name not in self.prompts:
            raise NotFoundError(body={"message": "Prompt not found"})
        return SimpleNamespace(name=name, prompt=self.prompts[name], version=1)

    def create_prompt(self, **kwargs: Any) -> None:
        self.created.append(kwargs)
        self.prompts[kwargs["name"]] = kwargs["prompt"]

    def flush(self) -> None:
        self.flushed = True


def push(client: FakeLangfuse, texts: Mapping[str, str], force: bool = False) -> dict[str, str]:
    return push_prompts(cast(Langfuse, client), texts, force=force)


def created(name: str, text: str) -> dict[str, Any]:
    return {
        "name": name,
        "prompt": text,
        "labels": ["production"],
        "type": "text",
        "commit_message": "make prompts-push",
    }


def test_creates_missing_prompts() -> None:
    client = FakeLangfuse()

    assert set(push(client, TEXTS).values()) == {"created"}
    assert client.created == [created(name, text) for name, text in TEXTS.items()]


def test_second_run_creates_nothing() -> None:
    client = FakeLangfuse()
    push(client, TEXTS)

    assert set(push(client, TEXTS).values()) == {"unchanged"}
    assert len(client.created) == len(TEXTS)


def test_edited_prompt_kept_without_force() -> None:
    client = FakeLangfuse(existing={NAME: "edited in Langfuse"})

    assert push(client, {NAME: "from file"}) == {NAME: "differs"}
    assert client.created == []


def test_force_creates_new_production_version() -> None:
    client = FakeLangfuse(existing={NAME: "edited in Langfuse"})

    assert push(client, {NAME: "from file"}, force=True) == {NAME: "updated"}
    assert client.created == [created(NAME, "from file")]


def test_force_leaves_unchanged_prompts_alone() -> None:
    client = FakeLangfuse(existing={NAME: "same"})

    assert push(client, {NAME: "same"}, force=True) == {NAME: "unchanged"}
    assert client.created == []


def test_non_404_error_creates_nothing() -> None:
    client = FakeLangfuse(error=ConnectionError("down"))

    result = push(client, {NAME: "x"})

    assert result[NAME].startswith("error")
    assert "down" in result[NAME]
    assert client.created == []


def test_main_reports_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeLangfuse(error=ConnectionError("down"))
    monkeypatch.setattr(push_module, "langfuse_client", lambda: client)

    assert main([]) == 1
    assert NAME in capsys.readouterr().out
    assert client.flushed


def test_main_succeeds_and_passes_force(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeLangfuse(existing={name: "edited" for name in TEXTS})
    monkeypatch.setattr(push_module, "langfuse_client", lambda: client)

    assert main(["--force"]) == 0
    assert len(client.created) == len(TEXTS)
    assert "updated" in capsys.readouterr().out


def test_main_without_keys(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def no_client() -> None:
        raise PromptsUnavailableError("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set")

    monkeypatch.setattr(push_module, "langfuse_client", no_client)

    assert main([]) == 1
    assert "LANGFUSE_PUBLIC_KEY" in capsys.readouterr().out
