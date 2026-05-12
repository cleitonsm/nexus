from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
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
