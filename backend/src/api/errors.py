from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .error_codes import error_body

from src.domain import (
    AccessDeniedError,
    ConcurrentChangeError,
    GroupDirectoryUnavailableError,
    InvalidFeedbackStateError,
    LLMCredentialInUseError,
    UsageLimitExceededError,
)


def register_error_handlers(app: FastAPI) -> None:
    """Recusa de acesso decidida por um caso de uso vira 403 (RN-21).

    Todo erro sai como ``{detail, code}`` (fix-14).
    """

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(error_body(exc.status_code, exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # RN-39: ``input`` (o corpo recebido) e ``ctx`` podem trazer a chave de
        # API digitada; o 422 so diz onde e por que, nunca o valor.
        errors = [
            {key: value for key, value in item.items() if key not in ("input", "ctx")}
            for item in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=jsonable_encoder(
                error_body(status.HTTP_422_UNPROCESSABLE_ENTITY, errors)
            ),
        )

    @app.exception_handler(AccessDeniedError)
    async def access_denied(_: Request, exc: AccessDeniedError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=error_body(status.HTTP_403_FORBIDDEN, str(exc)),
        )

    @app.exception_handler(GroupDirectoryUnavailableError)
    async def groups_unavailable(
        _: Request, exc: GroupDirectoryUnavailableError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_body(
                status.HTTP_503_SERVICE_UNAVAILABLE, "group directory unavailable"
            ),
        )

    @app.exception_handler(UsageLimitExceededError)
    async def usage_limited(_: Request, exc: UsageLimitExceededError) -> JSONResponse:
        return usage_limit_response(exc)

    @app.exception_handler(LLMCredentialInUseError)
    async def credential_in_use(_: Request, exc: LLMCredentialInUseError) -> JSONResponse:
        """RN-38: 409 com quem usa a credencial ou os modelos."""
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_body(
                status.HTTP_409_CONFLICT,
                {
                    "code": "llm_credential_in_use",
                    "message": str(exc),
                    "assistant_ids": list(exc.assistant_ids),
                    "models": list(exc.models),
                    "is_default": exc.is_default,
                },
            ),
        )

    @app.exception_handler(ConcurrentChangeError)
    async def concurrent_change(_: Request, exc: ConcurrentChangeError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_body(
                status.HTTP_409_CONFLICT,
                {"code": "concurrent_change", "message": str(exc)},
            ),
        )

    @app.exception_handler(InvalidFeedbackStateError)
    async def feedback_state(_: Request, exc: InvalidFeedbackStateError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_body(status.HTTP_409_CONFLICT, str(exc)),
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
