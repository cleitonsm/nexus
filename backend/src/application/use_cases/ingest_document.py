from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from uuid import uuid4

from src.application.dto import DocumentIngestionDTO
from src.domain import (
    AssistantId,
    CollectionName,
    Document,
    DocumentId,
    DocumentMetadata,
    DocumentRepository,
    EmbeddingGateway,
    VectorChunk,
    VectorStoreGateway,
)


@dataclass(frozen=True, slots=True)
class IngestDocumentInput:
    assistant_id: str
    source_name: str
    content: str
    metadata: dict[str, str] | None = None
    document_id: str | None = None
    chunk_size: int = 700
    chunk_overlap: int = 120


class IngestDocumentUseCase:
    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        embedding_gateway: EmbeddingGateway,
        vector_store_gateway: VectorStoreGateway,
    ) -> None:
        self._document_repository = document_repository
        self._embedding_gateway = embedding_gateway
        self._vector_store_gateway = vector_store_gateway

    def execute(self, data: IngestDocumentInput) -> DocumentIngestionDTO:
        chunks = _chunk_text(
            data.content,
            chunk_size=max(data.chunk_size, 1),
            chunk_overlap=max(min(data.chunk_overlap, data.chunk_size - 1), 0),
        )
        vectors = self._embedding_gateway.embed_texts(chunks)
        if len(vectors) != len(chunks):
            raise ValueError(
                "embedding provider returned an unexpected vector count."
            )

        document = self._document_repository.save(
            Document(
                id=DocumentId(data.document_id or str(uuid4())),
                assistant_id=AssistantId(data.assistant_id),
                source_name=data.source_name,
                content_hash=sha256(data.content.encode("utf-8")).hexdigest(),
                metadata=DocumentMetadata.from_dict(data.metadata),
            )
        )
        collection = CollectionName.from_assistant_id(document.assistant_id)

        embedding_dimension = len(vectors[0]) if vectors else 0
        if chunks and embedding_dimension > 0:
            self._vector_store_gateway.ensure_collection(
                collection_name=collection,
                vector_size=embedding_dimension,
            )
            self._vector_store_gateway.upsert_chunks(
                collection_name=collection,
                chunks=[
                    VectorChunk(
                        id=f"{document.id.value}:{chunk_index}",
                        document_id=document.id,
                        assistant_id=document.assistant_id,
                        chunk_index=chunk_index,
                        source_name=document.source_name,
                        content_hash=document.content_hash,
                        text=chunk_text,
                        vector=vectors[chunk_index],
                    )
                    for chunk_index, chunk_text in enumerate(chunks)
                ],
            )

        return DocumentIngestionDTO.from_entity(
            document,
            collection_name=collection.value,
            chunk_count=len(chunks),
            embedding_dimension=embedding_dimension,
        )


def _chunk_text(
    content: str,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    normalized = content.strip()
    if not normalized:
        raise ValueError("document content must not be empty.")

    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - chunk_overlap, start + 1)
    return chunks
