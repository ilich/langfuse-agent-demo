"""Hierarchical CrewAI crew: a manager delegates to order details, search and refund agents."""

from crewai import LLM, Agent, Crew, CrewOutput, Process, Task

from ..config import get_settings, get_today
from ..observability import trace_order_request
from .tools import make_order_tools

# CrewAI interpolates {message} and {today}; no other braces may appear in this text.
RESOLVE_REQUEST = """\
A customer of Acme Pte. Ltd. sent this message:

{message}

Today is {today}. If the customer gives a date without a year, use the most recent such date
on or before today.

Resolve the request by delegating to your specialists:

1. Identify the customer only from the identifiers in the message: customer ID, contact name,
   or contact name and company name. Pass them to the specialists exactly as the customer
   wrote them. If a specialist reports that no customer matches, ask the customer for their
   customer ID and stop.
2. For a refund request without an order ID, ask the order search specialist to find the
   order first. If several orders match, list them and ask the customer which one they mean.
   If none match, say so. Never pick one of several orders yourself.
3. Refund decisions must come from the refund policy specialist, who reads the refund policy,
   applies it to the order facts, and gets the amount from the refund calculation tool. Do not
   decide refunds from memory and do not do any arithmetic yourself.
4. Never mention any order or data belonging to anyone other than this customer.
"""

EXPECTED_ANSWER = """\
A reply to the customer in plain English. For order details: the order's dates, shipping
details and items. For searches: the matching orders. For refunds: whether the order is
eligible, which policy rules decided it, and the refund amount. If information is missing,
say exactly what the customer needs to provide.
"""


class AssistantUnavailableError(RuntimeError):
    """The crew cannot run, e.g. the model API key is not configured."""


def make_llm() -> LLM:
    settings = get_settings()
    if settings.gemini_api_key is None:
        raise AssistantUnavailableError("GEMINI_API_KEY is not configured")
    # Passed explicitly: pydantic-settings does not export .env values to os.environ.
    return LLM(model=settings.llm_model, api_key=settings.gemini_api_key.get_secret_value())


def build_crew(llm: LLM, verbose: bool = False) -> Crew:
    # Fresh tools per crew: they lock onto the first customer identified in this request.
    tools = make_order_tools()
    # crewai's AgentMeta hides Agent fields from the pydantic mypy plugin.
    details_agent = Agent(  # type: ignore[call-arg]
        role="Order details specialist",
        goal="Report the details, shipping and items of a customer's order accurately.",
        backstory=(
            "You look up orders for Acme Pte. Ltd. customer support. You only report what the "
            "order tool returns and never guess missing information."
        ),
        tools=[tools.get_order_details],
        llm=llm,
        allow_delegation=False,
        verbose=verbose,
    )
    # crewai's AgentMeta hides Agent fields from the pydantic mypy plugin.
    search_agent = Agent(  # type: ignore[call-arg]
        role="Order search specialist",
        goal="Find a customer's orders, optionally within a date range.",
        backstory=(
            "You search order history for Acme Pte. Ltd. customer support. You pass dates to "
            "the search tool as YYYY-MM-DD and report every matching order."
        ),
        tools=[tools.search_orders],
        llm=llm,
        allow_delegation=False,
        verbose=verbose,
    )
    # crewai's AgentMeta hides Agent fields from the pydantic mypy plugin.
    refund_agent = Agent(  # type: ignore[call-arg]
        role="Refund policy specialist",
        goal=(
            "Decide whether an order can be refunded by applying the shop's written refund "
            "policy to the order's facts, and explain the decision and the amount."
        ),
        backstory=(
            "You always read the current refund policy with the read_refund_policy tool before "
            "deciding, never rely on memory, take order facts from get_order_details, and get "
            "every amount from calculate_refund_amount instead of doing arithmetic."
        ),
        tools=[tools.read_refund_policy, tools.get_order_details, tools.calculate_refund_amount],
        llm=llm,
        allow_delegation=False,
        verbose=verbose,
    )
    task = Task(description=RESOLVE_REQUEST, expected_output=EXPECTED_ANSWER)
    return Crew(
        agents=[details_agent, search_agent, refund_agent],
        tasks=[task],
        process=Process.hierarchical,
        manager_llm=llm,
        verbose=verbose,
    )


def run_order_assistant(message: str) -> str:
    """Answer one customer message with a fresh crew."""
    crew = build_crew(make_llm(), verbose=get_settings().crew_verbose)
    # One Langfuse trace per request; the instrumented crew's spans nest under it.
    with trace_order_request(message) as record_answer:
        output = crew.kickoff(inputs={"message": message, "today": get_today().isoformat()})
        if not isinstance(output, CrewOutput):  # only returned when streaming, which is off
            raise AssistantUnavailableError("Unexpected streaming output from the crew")
        record_answer(output.raw)
    return output.raw
