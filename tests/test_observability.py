from collections.abc import Iterator
from pathlib import Path

import pytest
from openinference.instrumentation.crewai import CrewAIInstrumentor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from langfuse_agent_demo import observability
from langfuse_agent_demo.config import get_settings

LANGFUSE_SETTINGS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL")


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.chdir(tmp_path)  # ignore the developer's .env
    monkeypatch.setenv("NORTHWIND_DB_PATH", str(tmp_path / "northwind.db"))
    for name in LANGFUSE_SETTINGS:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    observability.shutdown_tracing()
    if CrewAIInstrumentor().is_instrumented_by_opentelemetry:
        CrewAIInstrumentor().uninstrument()
    get_settings.cache_clear()


@pytest.fixture
def langfuse_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    # Nothing listens here: the auth check fails fast and nothing leaves the machine.
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://127.0.0.1:9")
    get_settings.cache_clear()


def test_disabled_without_keys() -> None:
    assert observability.setup_tracing() is False
    assert not CrewAIInstrumentor().is_instrumented_by_opentelemetry


def test_request_span_is_a_noop_when_disabled() -> None:
    observability.setup_tracing()

    with observability.trace_order_request("hello") as record_answer:
        record_answer("hi")  # must not fail


@pytest.mark.usefixtures("langfuse_keys")
def test_enabled_with_keys_instruments_crewai() -> None:
    assert observability.setup_tracing() is True
    assert CrewAIInstrumentor().is_instrumented_by_opentelemetry
    # Idempotent: a second call doesn't instrument twice or fail.
    assert observability.setup_tracing() is True


@pytest.mark.usefixtures("langfuse_keys")
def test_request_span_records_message_and_answer() -> None:
    observability.setup_tracing()
    provider = trace.get_tracer_provider()
    assert isinstance(provider, TracerProvider)
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    with observability.trace_order_request("Refund order 14288") as record_answer:
        record_answer("Eligible")

    span = next(s for s in exporter.get_finished_spans() if s.name == "order-assistant")
    attributes = dict(span.attributes or {})
    assert "Refund order 14288" in str(attributes.get("langfuse.observation.input"))
    assert "Eligible" in str(attributes.get("langfuse.observation.output"))
