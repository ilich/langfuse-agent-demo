from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from langfuse_agent_demo.config import get_settings, get_today

OPTIONAL_SETTINGS = (
    "CURRENT_DATE",
    "REFUND_POLICY_PATH",
    "LLM_MODEL",
    "OPENAI_API_KEY",
    "CREW_VERBOSE",
)


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Settings built from the environment only, ignoring the developer's .env file."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NORTHWIND_DB_PATH", str(tmp_path / "northwind.db"))
    for name in OPTIONAL_SETTINGS:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_today_uses_current_date_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURRENT_DATE", "2023-11-20")
    assert get_today() == date(2023, 11, 20)


def test_today_defaults_to_real_date() -> None:
    assert get_today() == date.today()


def test_defaults() -> None:
    settings = get_settings()
    assert settings.llm_model == "openai/gpt-4o-mini"
    assert settings.refund_policy_path == Path("docs/refund-policy.md")
    assert settings.openai_api_key is None


def test_empty_values_count_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # .env.example ships with "OPENAI_API_KEY=" — that must not count as a configured key.
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("CURRENT_DATE", "")

    settings = get_settings()

    assert settings.openai_api_key is None
    assert settings.current_date is None


def test_crew_verbose_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    assert get_settings().crew_verbose is False

    monkeypatch.setenv("CREW_VERBOSE", "true")
    get_settings.cache_clear()

    assert get_settings().crew_verbose is True
