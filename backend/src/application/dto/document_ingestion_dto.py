from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain import Document


@dataclass(frozen=True, slots=True)
class DocumentIngestionDTO:
    id: str
    assistant_id: str
    source_name: str
    content_hash: str
    created_at: datetime
    collection_name: str
    chunk_count: int
    embedding_dimension: int

    @classmethod
    def from_entity(
        cls,
        document: Document,
        *,
        collection_name: str,
        chunk_count: int,
        embedding_dimension: int,
    ) -> "DocumentIngestionDTO":
        return cls(
            id=document.id.value,
            assistant_id=document.assistant_id.value,
            source_name=document.source_name,
            content_hash=document.content_hash,
            created_at=document.created_at,
            collection_name=collection_name,
            chunk_count=chunk_count,
            embedding_dimension=embedding_dimension,
        )
