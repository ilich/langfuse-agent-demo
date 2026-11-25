from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest
from crewai import LLM, Process
from crewai.llms.providers.openai.completion import OpenAICompletion

from langfuse_agent_demo.config import get_settings
from langfuse_agent_demo.crew.crew import (
    AssistantUnavailableError,
    build_crew,
    gateway_model_id,
    make_llm,
)
from langfuse_agent_demo.crew.prompts import CrewPrompts, PromptsUnavailableError
from langfuse_agent_demo.observability import TraceContextInterceptor


def test_crew_structure() -> None:
    crew = build_crew(LLM(model="openai/gpt-4o-mini", api_key="test-key"), CrewPrompts.from_file())

    assert crew.process == Process.hierarchical
    assert crew.manager_llm is not None
    tool_sets = [{t.name for t in agent.tools or []} for agent in crew.agents]
    assert tool_sets == [
        {"get_order_details"},
        {"search_orders"},
        {"read_refund_policy", "get_order_details", "calculate_refund_amount"},
    ]
    assert all(agent.allow_delegation is False for agent in crew.agents)
    assert crew.agents[2].role == CrewPrompts.from_file()["order-assistant/refund-agent/role"]
    assert len(crew.tasks) == 1
    assert "{message}" in crew.tasks[0].description
    assert "{today}" in crew.tasks[0].description


@pytest.fixture
def no_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.chdir(tmp_path)  # ignore the developer's .env
    monkeypatch.setenv("NORTHWIND_DB_PATH", str(tmp_path / "northwind.db"))
    for name in (
        "OPENAI_API_KEY",
        "LLM_MODEL",
        "LANGFUSE_GATEWAY_HOST",
        "LANGFUSE_GATEWAY_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


GATEWAY_HOST = "https://gateway.us.cloud.langfuse.com"


@pytest.mark.usefixtures("no_api_key")
def test_make_llm_uses_gateway_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_GATEWAY_HOST", GATEWAY_HOST + "/")
    monkeypatch.setenv("LANGFUSE_GATEWAY_KEY", "gw-key")
    get_settings.cache_clear()

    llm = make_llm()  # no OPENAI_API_KEY needed: the gateway holds the provider key

    assert isinstance(llm, OpenAICompletion)
    assert llm.model == "openai:gpt-4o-mini"
    assert llm.base_url == GATEWAY_HOST + "/openai/v1"
    assert llm.api_key == "gw-key"
    assert isinstance(llm.interceptor, TraceContextInterceptor)


@pytest.mark.usefixtures("no_api_key")
def test_gateway_uses_llm_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_GATEWAY_HOST", GATEWAY_HOST)
    monkeypatch.setenv("LANGFUSE_GATEWAY_KEY", "gw-key")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4.1-mini")
    get_settings.cache_clear()

    assert make_llm().model == "openai:gpt-4.1-mini"


@pytest.mark.parametrize(
    ("llm_model", "gateway_id"),
    [
        ("openai/gpt-4o-mini", "openai:gpt-4o-mini"),
        ("gpt-4o-mini", "openai:gpt-4o-mini"),
        ("anthropic/claude-sonnet-5-5", "anthropic:claude-sonnet-5-5"),
    ],
)
def test_gateway_model_id(llm_model: str, gateway_id: str) -> None:
    assert gateway_model_id(llm_model) == gateway_id


@pytest.mark.usefixtures("no_api_key")
def test_make_llm_calls_openai_directly_without_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    get_settings.cache_clear()

    llm = make_llm()

    assert isinstance(llm, OpenAICompletion)
    assert llm.model == "gpt-4o-mini"
    assert llm.api_key == "openai-key"
    assert llm.base_url is None
    assert llm.interceptor is None


@pytest.mark.usefixtures("no_api_key")
def test_make_llm_requires_key() -> None:
    with pytest.raises(AssistantUnavailableError):
        make_llm()


def test_agents_in_one_crew_share_tools() -> None:
    # The details agent and the refund agent must share one customer lock.
    crew = build_crew(LLM(model="openai/gpt-4o-mini", api_key="test-key"), CrewPrompts.from_file())
    details_tool = crew.agents[0].tools[0]  # type: ignore[index]
    refund_details_tool = next(
        t for t in crew.agents[2].tools or [] if t.name == "get_order_details"
    )

    assert details_tool is refund_details_tool


@pytest.mark.parametrize("verbose", [True, False])
def test_verbose_reaches_crew_and_agents(verbose: bool) -> None:
    crew = build_crew(
        LLM(model="openai/gpt-4o-mini", api_key="test-key"),
        CrewPrompts.from_file(),
        verbose=verbose,
    )

    assert crew.verbose is verbose
    assert all(agent.verbose is verbose for agent in crew.agents)


def test_run_is_wrapped_in_a_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    from collections.abc import Callable
    from contextlib import contextmanager

    from crewai import CrewOutput

    from langfuse_agent_demo.crew import crew as crew_module

    recorded: dict[str, object] = {}
    prompts = CrewPrompts(texts={}, versions={"x": 2})

    @contextmanager
    def fake_trace(
        message: str, prompt_versions: Mapping[str, int]
    ) -> Iterator[Callable[[str], None]]:
        recorded["message"] = message
        recorded["prompt_versions"] = prompt_versions
        yield lambda answer: recorded.__setitem__("answer", answer)

    class FakeCrew:
        def kickoff(self, inputs: dict[str, str]) -> CrewOutput:
            return CrewOutput(raw=f"answer to {inputs['message']}")

    monkeypatch.setattr(crew_module, "langfuse_client", lambda: "client")
    monkeypatch.setattr(
        crew_module, "fetch_prompts", lambda client: prompts if client == "client" else None
    )
    monkeypatch.setattr(crew_module, "make_llm", lambda: None)
    monkeypatch.setattr(
        crew_module,
        "build_crew",
        lambda llm, crew_prompts, verbose=False: FakeCrew() if crew_prompts is prompts else None,
    )
    monkeypatch.setattr(crew_module, "trace_order_request", fake_trace)

    answer = crew_module.run_order_assistant("Refund order 14288")

    assert answer == "answer to Refund order 14288"
    assert recorded == {
        "message": "Refund order 14288",
        "prompt_versions": {"x": 2},
        "answer": answer,
    }


def test_run_fails_when_prompts_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from langfuse_agent_demo.crew import crew as crew_module

    def no_client() -> None:
        raise PromptsUnavailableError("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set")

    def unexpected_llm() -> None:
        raise AssertionError("make_llm must not run without prompts")

    monkeypatch.setattr(crew_module, "langfuse_client", no_client)
    monkeypatch.setattr(crew_module, "make_llm", unexpected_llm)

    with pytest.raises(PromptsUnavailableError):
        crew_module.run_order_assistant("Refund order 14288")
