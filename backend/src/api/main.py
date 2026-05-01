from __future__ import annotations

from contextlib import asynccontextmanager
import json
from pathlib import Path
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from sqlalchemy import inspect, text

from src.api.routes import (
    admin_router,
    assistants_router,
    conversations_router,
    documents_router,
)
from src.infrastructure.database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Fase inicial: garante schema mínimo até termos migrações automáticas.
    Base.metadata.create_all(bind=engine)
    _ensure_incremental_columns()
    yield

app = FastAPI(title="Nexus API", version="0.1.0", lifespan=lifespan)
app.include_router(admin_router)
app.include_router(assistants_router)
app.include_router(conversations_router)
app.include_router(documents_router)


def _agent_debug_log(
    *,
    run_id: str,
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict[str, object],
) -> None:
    payload = {
        "sessionId": "a1f259",
        "id": f"log_{int(time.time() * 1000)}_{uuid4().hex[:8]}",
        "timestamp": int(time.time() * 1000),
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
    }
    try:
        with Path("debug-a1f259.log").open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except OSError:
        pass


@app.middleware("http")
async def _agent_log_document_upload(
    request: Request,
    call_next,
):
    if request.method == "POST" and request.url.path.endswith("/documents"):
        # region agent log
        _agent_debug_log(
            run_id="pre-fix",
            hypothesis_id="H1,H2,H4",
            location="backend/src/api/main.py:_agent_log_document_upload:entry",
            message="backend received document upload request",
            data={
                "path": request.url.path,
                "contentLength": request.headers.get("content-length"),
                "contentType": request.headers.get("content-type", "").split(";")[0],
            },
        )
        # endregion
        response = await call_next(request)
        # region agent log
        _agent_debug_log(
            run_id="pre-fix",
            hypothesis_id="H2,H4",
            location="backend/src/api/main.py:_agent_log_document_upload:exit",
            message="backend finished document upload request",
            data={"path": request.url.path, "statusCode": response.status_code},
        )
        # endregion
        return response
    return await call_next(request)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _ensure_incremental_columns() -> None:
    inspector = inspect(engine)
    if "assistants" not in inspector.get_table_names():
        return
    columns = {
        column["name"]
        for column in inspector.get_columns("assistants")
    }
    if "initial_prompt" in columns:
        return
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE assistants ADD COLUMN initial_prompt TEXT")
        )
