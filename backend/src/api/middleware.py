from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from src.domain import MetricsRecorder, NoopMetrics, NoopTracer, Tracer
from src.infrastructure.observability import (
    bind_request_id,
    normalize_request_id,
    reset_request_id,
)

REQUEST_ID_HEADER = "X-Request-ID"
# /metrics e /health nao geram trecho: sao consultados a cada poucos segundos.
_UNTRACED_PATHS = frozenset({"/metrics", "/health"})

logger = logging.getLogger(__name__)


def register_request_context(
    app: FastAPI,
    *,
    tracer: Tracer | None = None,
    metrics: MetricsRecorder | None = None,
) -> None:
    """Associa um identificador a cada requisicao e o devolve no cabecalho.

    SPEC-006: cada requisicao vira o trecho raiz do rastreamento, cujo
    identificador e o proprio ``X-Request-ID`` (RNF-29), e alimenta as
    metricas HTTP, rotuladas pelo modelo da rota (nunca pelo caminho real,
    que carrega identificadores).
    """
    tracer = tracer or NoopTracer()
    metrics = metrics or NoopMetrics()

    @app.middleware("http")
    async def request_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = normalize_request_id(request.headers.get(REQUEST_ID_HEADER))
        token = bind_request_id(request_id)
        started_at = time.perf_counter()
        traced = request.url.path not in _UNTRACED_PATHS
        try:
            if not traced:
                response = await call_next(request)
            else:
                with tracer.span(
                    "http.request",
                    {"http.method": request.method},
                ) as span:
                    response = await call_next(request)
                    span.set_attribute("http.route", _route(request))
                    span.set_attribute("http.status_code", response.status_code)
        except Exception:
            logger.exception(
                "http.request.failed",
                extra=_request_fields(request, started_at),
            )
            _record(metrics, request, 500, started_at)
            raise
        else:
            logger.info(
                "http.request.finished",
                extra={
                    **_request_fields(request, started_at),
                    "status_code": response.status_code,
                },
            )
            if traced:
                _record(metrics, request, response.status_code, started_at)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            reset_request_id(token)


def _route(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


def _record(
    metrics: MetricsRecorder,
    request: Request,
    status_code: int,
    started_at: float,
) -> None:
    route = _route(request)
    metrics.increment(
        "nexus_http_requests_total",
        labels={
            "method": request.method,
            "route": route,
            "status": str(status_code),
        },
    )
    metrics.observe(
        "nexus_http_request_duration_seconds",
        time.perf_counter() - started_at,
        {"method": request.method, "route": route},
    )


def _request_fields(request: Request, started_at: float) -> dict[str, object]:
    return {
        "http_method": request.method,
        "http_path": request.url.path,
        "duration_ms": round((time.perf_counter() - started_at) * 1000),
    }
