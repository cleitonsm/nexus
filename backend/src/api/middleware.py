from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from src.infrastructure.observability import (
    bind_request_id,
    normalize_request_id,
    reset_request_id,
)

REQUEST_ID_HEADER = "X-Request-ID"

logger = logging.getLogger(__name__)


def register_request_context(app: FastAPI) -> None:
    """Associa um identificador a cada requisicao e o devolve no cabecalho."""

    @app.middleware("http")
    async def request_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = normalize_request_id(request.headers.get(REQUEST_ID_HEADER))
        token = bind_request_id(request_id)
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "http.request.failed",
                extra=_request_fields(request, started_at),
            )
            raise
        else:
            logger.info(
                "http.request.finished",
                extra={
                    **_request_fields(request, started_at),
                    "status_code": response.status_code,
                },
            )
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            reset_request_id(token)


def _request_fields(request: Request, started_at: float) -> dict[str, object]:
    return {
        "http_method": request.method,
        "http_path": request.url.path,
        "duration_ms": round((time.perf_counter() - started_at) * 1000),
    }
