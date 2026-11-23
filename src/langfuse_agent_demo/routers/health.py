import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import Engine, select
from sqlalchemy.exc import SQLAlchemyError

from ..db import Order, get_engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    success: bool
    error: str | None = None


@router.get("/health", response_model_exclude_none=True)
def health(response: Response, engine: Annotated[Engine, Depends(get_engine)]) -> HealthResponse:
    try:
        with engine.connect() as conn:
            # Query a real table so an empty or wrong database file is reported as unhealthy.
            conn.execute(select(Order.order_id).limit(1))
    except SQLAlchemyError:
        logger.exception("Health check: database is not accessible")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(success=False, error="Database is not accessible")
    return HealthResponse(success=True)
