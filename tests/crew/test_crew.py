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


def test_agents_in_one_crew_share_tools() -> None:
    # The details agent and the refund agent must share one customer lock.
    crew = build_crew(LLM(model="gemini/gemini-2.5-flash", api_key="test-key"))
    details_tool = crew.agents[0].tools[0]  # type: ignore[index]
    refund_details_tool = next(
        t for t in crew.agents[2].tools or [] if t.name == "get_order_details"
    )

    assert details_tool is refund_details_tool


@pytest.mark.parametrize("verbose", [True, False])
def test_verbose_reaches_crew_and_agents(verbose: bool) -> None:
    crew = build_crew(LLM(model="gemini/gemini-2.5-flash", api_key="test-key"), verbose=verbose)

    assert crew.verbose is verbose
    assert all(agent.verbose is verbose for agent in crew.agents)


def test_run_is_wrapped_in_a_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    from collections.abc import Callable
    from contextlib import contextmanager

    from crewai import CrewOutput

    from langfuse_agent_demo.crew import crew as crew_module

    recorded: dict[str, str] = {}

    @contextmanager
    def fake_trace(message: str) -> Iterator[Callable[[str], None]]:
        recorded["message"] = message
        yield lambda answer: recorded.__setitem__("answer", answer)

    class FakeCrew:
        def kickoff(self, inputs: dict[str, str]) -> CrewOutput:
            return CrewOutput(raw=f"answer to {inputs['message']}")

    monkeypatch.setattr(crew_module, "make_llm", lambda: None)
    monkeypatch.setattr(crew_module, "build_crew", lambda llm, verbose=False: FakeCrew())
    monkeypatch.setattr(crew_module, "trace_order_request", fake_trace)

    answer = crew_module.run_order_assistant("Refund order 14288")

    assert answer == "answer to Refund order 14288"
    assert recorded == {"message": "Refund order 14288", "answer": answer}
