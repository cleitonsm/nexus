from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes import assistants_router, conversations_router
from src.infrastructure.database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Fase inicial: garante schema mínimo até termos migrações automáticas.
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title="Nexus API", version="0.1.0", lifespan=lifespan)
app.include_router(assistants_router)
app.include_router(conversations_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
