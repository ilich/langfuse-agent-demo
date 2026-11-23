import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StringConstraints

from ..crew.crew import run_order_assistant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["orders"])

UNAVAILABLE = "The order assistant is unavailable. Please try again later."


class AssistRequest(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class AssistResponse(BaseModel):
    answer: str


class ErrorResponse(BaseModel):
    error: str


def get_assistant() -> Callable[[str], str]:
    return run_order_assistant


@router.post(
    "/assist",
    response_model=AssistResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}},
)
def assist(
    request: AssistRequest, assistant: Annotated[Callable[[str], str], Depends(get_assistant)]
) -> AssistResponse | JSONResponse:
    """Answer a customer's plain-English question about their orders or a refund."""
    # Plain def: the crew is synchronous, so FastAPI runs this in its thread pool.
    try:
        answer = assistant(request.message)
    except Exception:
        logger.exception("Order assistant failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(error=UNAVAILABLE).model_dump(),
        )
    return AssistResponse(answer=answer)
