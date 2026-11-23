from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    success: bool
    error: str | None = None


@router.get("/health", response_model_exclude_none=True)
async def health() -> HealthResponse:
    return HealthResponse(success=True)
