from __future__ import annotations

from hashlib import sha256

from src.domain import (
    AssistantId,
    DocumentChunker,
    DocumentExtractor,
    DocumentId,
    EmbeddingGateway,
    SparseEmbeddingGateway,
    VectorChunk,
)

# Muda sempre que extracao, chunking ou metadados dos chunks mudarem de forma
# que exija reindexar (RF-32).
# "3": chunks passam a levar o vetor esparso da busca hibrida (SPEC-003).
PIPELINE_VERSION = "3"


def hash_content(raw_content: bytes) -> str:
    return sha256(raw_content).hexdigest()


class DocumentIndexer:
    """Extrai, fragmenta e vetoriza um arquivo; usado na ingestao e na reindexacao."""

    def __init__(
        self,
        *,
        extractor: DocumentExtractor,
        chunker: DocumentChunker,
        embedding_gateway: EmbeddingGateway,
        sparse_embedding_gateway: SparseEmbeddingGateway,
    ) -> None:
        self._extractor = extractor
        self._chunker = chunker
        self._embedding_gateway = embedding_gateway
        self._sparse_embedding_gateway = sparse_embedding_gateway

    @property
    def embedding_model(self) -> str:
        return self._embedding_gateway.model_name

    @property
    def embedding_dimension(self) -> int:
        return self._embedding_gateway.dimension

    def build_chunks(
        self,
        *,
        assistant_id: AssistantId,
        document_id: DocumentId,
        source_name: str,
        content_type: str | None,
        raw_content: bytes,
    ) -> list[VectorChunk]:
        extracted = self._extractor.extract(
            filename=source_name,
            content_type=content_type,
            raw_content=raw_content,
        )
        chunks = self._chunker.chunk(extracted)
        texts = [chunk.text for chunk in chunks]
        vectors = self._embedding_gateway.embed_documents(texts)
        sparse_vectors = self._sparse_embedding_gateway.embed_documents(texts)
        if len(vectors) != len(chunks) or len(sparse_vectors) != len(chunks):
            raise ValueError(
                "embedding provider returned an unexpected vector count."
            )
        content_hash = hash_content(raw_content)
        return [
            VectorChunk(
                id=f"{document_id.value}:{chunk.index}",
                document_id=document_id,
                assistant_id=assistant_id,
                chunk_index=chunk.index,
                source_name=source_name,
                content_hash=content_hash,
                text=chunk.text,
                vector=vector,
                section_path=chunk.section_label,
                page=chunk.page,
                embedding_model=self.embedding_model,
                pipeline_version=PIPELINE_VERSION,
                sparse_vector=sparse_vector,
            )
            for chunk, vector, sparse_vector in zip(chunks, vectors, sparse_vectors)
        ]
