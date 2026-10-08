from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.domain import AccessDeniedError


def register_error_handlers(app: FastAPI) -> None:
    """Recusa de acesso decidida por um caso de uso vira 403 (RN-21)."""

    @app.exception_handler(AccessDeniedError)
    async def access_denied(_: Request, exc: AccessDeniedError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": str(exc)},
        )
