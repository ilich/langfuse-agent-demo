from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .routers import health, orders


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_settings()  # fail fast at startup if required settings (e.g. in .env) are missing
    yield


app = FastAPI(title="langfuse-agent-demo", lifespan=lifespan)

app.include_router(health.router)
app.include_router(orders.router)
