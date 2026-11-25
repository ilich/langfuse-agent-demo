from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .access_log import quiet_health_checks
from .config import get_settings
from .observability import setup_tracing, shutdown_tracing
from .routers import health, orders


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_settings()  # fail fast at startup if required settings (e.g. in .env) are missing
    # Langfuse + CrewAI instrumentation must be in place before any crew runs.
    setup_tracing()
    yield
    shutdown_tracing()


# The client polls /health; keep those requests out of the console (failures still show).
quiet_health_checks()

app = FastAPI(title="langfuse-agent-demo", lifespan=lifespan)

app.include_router(health.router)
app.include_router(orders.router)
