from collections.abc import Iterator
from pathlib import Path

import pytest
from crewai import LLM, Process

from langfuse_agent_demo.config import get_settings
from langfuse_agent_demo.crew.crew import AssistantUnavailableError, build_crew, make_llm


def test_crew_structure() -> None:
    crew = build_crew(LLM(model="gemini/gemini-2.5-flash", api_key="test-key"))

    assert crew.process == Process.hierarchical
    assert crew.manager_llm is not None
    tool_sets = [{t.name for t in agent.tools or []} for agent in crew.agents]
    assert tool_sets == [
        {"get_order_details"},
        {"search_orders"},
        {"read_refund_policy", "get_order_details", "calculate_refund_amount"},
    ]
    assert all(agent.allow_delegation is False for agent in crew.agents)
    assert len(crew.tasks) == 1
    assert "{message}" in crew.tasks[0].description
    assert "{today}" in crew.tasks[0].description


@pytest.fixture
def no_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.chdir(tmp_path)  # ignore the developer's .env
    monkeypatch.setenv("NORTHWIND_DB_PATH", str(tmp_path / "northwind.db"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.usefixtures("no_api_key")
def test_make_llm_requires_key() -> None:
    with pytest.raises(AssistantUnavailableError):
        make_llm()
