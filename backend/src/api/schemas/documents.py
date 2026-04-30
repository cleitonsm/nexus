from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DocumentIngestionResponse(BaseModel):
    id: str
    assistant_id: str
    source_name: str
    content_hash: str
    created_at: datetime
    collection_name: str
    chunk_count: int
    embedding_dimension: int
