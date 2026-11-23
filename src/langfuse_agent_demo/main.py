from fastapi import FastAPI

from .routers import health

app = FastAPI(title="langfuse-agent-demo")

app.include_router(health.router)
