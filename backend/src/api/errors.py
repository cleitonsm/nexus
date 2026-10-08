from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.domain import (
    AccessDeniedError,
    GroupDirectoryUnavailableError,
    InvalidFeedbackStateError,
    UsageLimitExceededError,
)


def register_error_handlers(app: FastAPI) -> None:
    """Recusa de acesso decidida por um caso de uso vira 403 (RN-21)."""

    @app.exception_handler(AccessDeniedError)
    async def access_denied(_: Request, exc: AccessDeniedError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": str(exc)},
        )

    @app.exception_handler(GroupDirectoryUnavailableError)
    async def groups_unavailable(
        _: Request, exc: GroupDirectoryUnavailableError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "group directory unavailable"},
        )

    @app.exception_handler(UsageLimitExceededError)
    async def usage_limited(_: Request, exc: UsageLimitExceededError) -> JSONResponse:
        return usage_limit_response(exc)

    @app.exception_handler(InvalidFeedbackStateError)
    async def feedback_state(_: Request, exc: InvalidFeedbackStateError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )


def usage_limit_response(
    exc: UsageLimitExceededError,
    now: datetime | None = None,
) -> JSONResponse:
    """RN-32: 429 com o instante em que a proxima pergunta sera aceita."""
    current = now or datetime.now(UTC)
    wait_seconds = max(int((exc.retry_at - current).total_seconds()) + 1, 1)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        headers={"Retry-After": str(wait_seconds)},
        content={
            "detail": "Limite de perguntas atingido.",
            "code": "usage_limit",
            "window": exc.window,
            "limit": exc.limit,
            "retry_at": exc.retry_at.isoformat(),
            "retry_after_seconds": wait_seconds,
        },
    )
