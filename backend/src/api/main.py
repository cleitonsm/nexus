from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from src.api.dependencies import get_vector_store_gateway
from src.api.errors import register_error_handlers
from src.api.routes import (
    admin_router,
    assistants_router,
    conversations_router,
    document_access_router,
    documents_router,
    feedback_router,
    index_router,
    me_router,
)
from src.api.middleware import register_request_context
from src.application.use_cases import FailInterruptedReindexesUseCase
from src.infrastructure.composition import (
    api_docs_enabled,
    build_metrics,
    build_tracer,
    cors_allowed_origins,
)
from src.infrastructure.database import (
    PostgresReindexJobRepository,
    SessionLocal,
    ingestion_job_gauges,
    run_migrations,
)
from src.infrastructure.observability import configure_logging

configure_logging(level=os.getenv("LOG_LEVEL", "INFO"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    # As migracoes sao aplicadas antes de a API aceitar requisicoes (ADR 0011).
    run_migrations()
    _fail_interrupted_reindexes()
    yield


# Toda rota exige token, exceto /health (RF-40). A documentacao interativa
# tambem nao exige e por isso so e publicada no ambiente local.
_docs = api_docs_enabled()
app = FastAPI(
    title="Nexus API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs else None,
    redoc_url="/redoc" if _docs else None,
    openapi_url="/openapi.json" if _docs else None,
)
register_request_context(app, tracer=build_tracer(), metrics=build_metrics())
register_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins(),
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Retry-After"],
)
app.include_router(admin_router)
app.include_router(assistants_router)
app.include_router(conversations_router)
app.include_router(document_access_router)
app.include_router(documents_router)
app.include_router(feedback_router)
app.include_router(index_router)
app.include_router(me_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Jobs de ingestao por estado, lidos do banco a cada coleta (o worker roda
# em outro processo e nao expoe metricas proprias).
build_metrics().register_collector(lambda: ingestion_job_gauges(SessionLocal))


@app.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def metrics() -> PlainTextResponse:
    """RF-57, D2: formato de texto do Prometheus, sem token.

    Fica fora do proxy do frontend (o Nginx responde 404 em ``/api/metrics``);
    o Prometheus do perfil ``observabilidade`` le pela rede interna do Compose.
    So contagens, duracoes e rotulos de baixa cardinalidade (RNF-25).
    """
    return PlainTextResponse(
        build_metrics().render(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


def _fail_interrupted_reindexes() -> None:
    """Reindexacao interrompida por reinicio vira falha; o alias nao muda."""
    with SessionLocal() as session:
        FailInterruptedReindexesUseCase(
            vector_store_gateway=get_vector_store_gateway(),
            reindex_job_repository=PostgresReindexJobRepository(session=session),
        ).execute()
