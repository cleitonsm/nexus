from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReindexJobResponse(BaseModel):
    id: str
    assistant_id: str
    status: str
    target_collection: str
    total_documents: int
    processed_documents: int
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class IndexStatusResponse(BaseModel):
    assistant_id: str
    embedding_model: str
    pipeline_version: str
    collection_name: str | None
    outdated: bool
    documents_total: int
    documents_indexed: int
    documents_without_original: list[str]
    last_reindex: ReindexJobResponse | None
