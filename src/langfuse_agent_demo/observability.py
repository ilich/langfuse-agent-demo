"""Langfuse tracing for the CrewAI crew.

Follows https://langfuse.com/integrations/frameworks/crewai: create the Langfuse client (which
becomes the global OpenTelemetry tracer provider), check the credentials, and instrument CrewAI
with OpenInference before any crew runs. Tracing is enabled only when LANGFUSE_PUBLIC_KEY and
LANGFUSE_SECRET_KEY are set; otherwise every function here is a no-op.
"""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import httpx
from crewai.llms.hooks.base import BaseInterceptor
from langfuse import Langfuse, get_client, propagate_attributes
from openinference.instrumentation.crewai import CrewAIInstrumentor
from opentelemetry.propagate import inject

from .config import get_settings

logger = logging.getLogger(__name__)

_enabled = False


def setup_tracing() -> bool:
    """Initialise Langfuse and instrument CrewAI. Returns whether tracing is enabled."""
    global _enabled
    settings = get_settings()
    if settings.langfuse_public_key is None or settings.langfuse_secret_key is None:
        logger.info("Langfuse tracing disabled: LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set")
        return False

    # Pass the keys explicitly: pydantic-settings does not export .env values to os.environ.
    langfuse = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        base_url=settings.langfuse_base_url,
    )
    if not _enabled:
        # A tracing problem must never stop the app; auth_check raises on network errors.
        try:
            authenticated = langfuse.auth_check()
        except Exception:
            authenticated = False
        if authenticated:
            logger.info("Langfuse client is authenticated (%s)", settings.langfuse_base_url)
        else:
            logger.warning(
                "Langfuse authentication failed; check the keys and LANGFUSE_BASE_URL (%s)",
                settings.langfuse_base_url,
            )
    instrumentor = CrewAIInstrumentor()
    if not instrumentor.is_instrumented_by_opentelemetry:
        instrumentor.instrument(skip_dep_check=True)
    _enabled = True
    return True


def shutdown_tracing() -> None:
    """Send any buffered spans to Langfuse; call on application shutdown."""
    global _enabled
    if _enabled:
        get_client().flush()
        _enabled = False


@contextmanager
def trace_order_request(message: str) -> Iterator[Callable[[str], None]]:
    """Wrap one crew run in a Langfuse span; yields a function that records the answer."""
    if not _enabled:
        yield lambda answer: None
        return

    with (
        get_client().start_as_current_observation(
            as_type="span", name="order-assistant", input={"message": message}
        ) as span,
        propagate_attributes(tags=["order-assistant"]),
    ):

        def record_answer(answer: str) -> None:
            span.update(output={"answer": answer})

        yield record_answer


class TraceContextInterceptor(BaseInterceptor[httpx.Request, httpx.Response]):
    """Adds the current span's W3C ``traceparent`` to outgoing model requests.

    The Langfuse AI Gateway records each model call as a generation; with ``traceparent`` it
    nests that generation under the calling CrewAI span instead of starting a separate trace.
    """

    def on_outbound(self, message: httpx.Request) -> httpx.Request:
        headers: dict[str, str] = {}
        inject(headers)  # no-op outside a span
        message.headers.update(headers)
        return message

    def on_inbound(self, message: httpx.Response) -> httpx.Response:
        return message

    async def aon_outbound(self, message: httpx.Request) -> httpx.Request:
        return self.on_outbound(message)

    async def aon_inbound(self, message: httpx.Response) -> httpx.Response:
        return message
