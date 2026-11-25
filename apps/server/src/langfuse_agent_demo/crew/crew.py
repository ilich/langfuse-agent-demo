"""Hierarchical CrewAI crew: a manager delegates to order details, search and refund agents.

All prompts come from Langfuse prompt management (see ``prompts.py``); ``prompts.toml`` holds the
versions that ``make prompts-push`` loads into Langfuse.
"""

from crewai import LLM, Agent, Crew, CrewOutput, Process, Task

from ..config import get_settings, get_today
from ..observability import TraceContextInterceptor, trace_order_request
from .prompts import CrewPrompts, fetch_prompts, langfuse_client
from .tools import make_order_tools


class AssistantUnavailableError(RuntimeError):
    """The crew cannot run, e.g. the model API key is not configured."""


def gateway_model_id(llm_model: str) -> str:
    """Gateway model ID ``<connection>:<model>`` for a CrewAI ``<provider>/<model>`` name.

    Assumes the gateway connection is named after the provider, e.g. ``openai/gpt-4o-mini``
    becomes ``openai:gpt-4o-mini``. A name without a provider is an OpenAI model, as in CrewAI.
    """
    provider, _, model = llm_model.rpartition("/")
    return f"{provider or 'openai'}:{model}"


def make_llm() -> LLM:
    settings = get_settings()
    if settings.langfuse_gateway_host and settings.langfuse_gateway_key:
        # Langfuse AI Gateway: OpenAI-compatible endpoint that holds the provider key and
        # records every call; traceparent nests those calls under the CrewAI spans.
        return LLM(
            # "openai/" selects CrewAI's OpenAI provider, which speaks the gateway's API.
            model=f"openai/{gateway_model_id(settings.llm_model)}",
            base_url=f"{settings.langfuse_gateway_host.rstrip('/')}/openai/v1",
            api_key=settings.langfuse_gateway_key.get_secret_value(),
            interceptor=TraceContextInterceptor(),
        )
    if settings.openai_api_key is None:
        raise AssistantUnavailableError("OPENAI_API_KEY is not configured")
    # Passed explicitly: pydantic-settings does not export .env values to os.environ.
    return LLM(model=settings.llm_model, api_key=settings.openai_api_key.get_secret_value())


def build_crew(llm: LLM, prompts: CrewPrompts, verbose: bool = False) -> Crew:
    # Fresh tools per crew: they lock onto the first customer identified in this request.
    tools = make_order_tools()
    # crewai's AgentMeta hides Agent fields from the pydantic mypy plugin.
    details_agent = Agent(  # type: ignore[call-arg]
        role=prompts["order-assistant/details-agent/role"],
        goal=prompts["order-assistant/details-agent/goal"],
        backstory=prompts["order-assistant/details-agent/backstory"],
        tools=[tools.get_order_details],
        llm=llm,
        allow_delegation=False,
        verbose=verbose,
    )
    # crewai's AgentMeta hides Agent fields from the pydantic mypy plugin.
    search_agent = Agent(  # type: ignore[call-arg]
        role=prompts["order-assistant/search-agent/role"],
        goal=prompts["order-assistant/search-agent/goal"],
        backstory=prompts["order-assistant/search-agent/backstory"],
        tools=[tools.search_orders],
        llm=llm,
        allow_delegation=False,
        verbose=verbose,
    )
    # crewai's AgentMeta hides Agent fields from the pydantic mypy plugin.
    refund_agent = Agent(  # type: ignore[call-arg]
        role=prompts["order-assistant/refund-agent/role"],
        goal=prompts["order-assistant/refund-agent/goal"],
        backstory=prompts["order-assistant/refund-agent/backstory"],
        tools=[tools.read_refund_policy, tools.get_order_details, tools.calculate_refund_amount],
        llm=llm,
        allow_delegation=False,
        verbose=verbose,
    )
    # CrewAI interpolates {message} and {today} into the task description at kickoff.
    task = Task(
        description=prompts["order-assistant/resolve-request"],
        expected_output=prompts["order-assistant/expected-answer"],
    )
    return Crew(
        agents=[details_agent, search_agent, refund_agent],
        tasks=[task],
        process=Process.hierarchical,
        manager_llm=llm,
        verbose=verbose,
    )


def run_order_assistant(message: str) -> str:
    """Answer one customer message with a fresh crew."""
    # Prompts first: without them there is nothing to run (Langfuse caches them for 60 s).
    prompts = fetch_prompts(langfuse_client())
    crew = build_crew(make_llm(), prompts, verbose=get_settings().crew_verbose)
    # One Langfuse trace per request; the instrumented crew's spans nest under it.
    with trace_order_request(message, prompts.versions) as record_answer:
        output = crew.kickoff(inputs={"message": message, "today": get_today().isoformat()})
        if not isinstance(output, CrewOutput):  # only returned when streaming, which is off
            raise AssistantUnavailableError("Unexpected streaming output from the crew")
        record_answer(output.raw)
    return output.raw
