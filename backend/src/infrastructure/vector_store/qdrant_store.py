from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.http import models

from src.domain import CollectionName, DocumentId, SearchResult, VectorChunk


class QdrantVectorStoreGateway:
    def __init__(self, *, url: str, api_key: str | None = None) -> None:
        self._client = QdrantClient(url=url, api_key=api_key or None)

    def ensure_collection(
        self,
        collection_name: CollectionName,
        vector_size: int,
    ) -> None:
        if vector_size <= 0:
            raise ValueError("vector_size must be positive.")
        if self._client.collection_exists(collection_name=collection_name.value):
            return
        self._client.create_collection(
            collection_name=collection_name.value,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    def upsert_chunks(
        self,
        collection_name: CollectionName,
        chunks: list[VectorChunk],
    ) -> None:
        if not chunks:
            return
        self._client.upsert(
            collection_name=collection_name.value,
            points=[
                models.PointStruct(
                    id=str(uuid5(NAMESPACE_URL, chunk.id)),
                    vector=chunk.vector,
                    payload={
                        "chunk_id": chunk.id,
                        "assistant_id": chunk.assistant_id.value,
                        "document_id": chunk.document_id.value,
                        "chunk_index": chunk.chunk_index,
                        "source_name": chunk.source_name,
                        "content_hash": chunk.content_hash,
                        "text": chunk.text,
                    },
                )
                for chunk in chunks
            ],
            wait=True,
        )

    def search(
        self,
        collection_name: CollectionName,
        query_vector: list[float],
        limit: int,
    ) -> list[SearchResult]:
        if limit <= 0:
            return []
        if hasattr(self._client, "search"):
            hits = self._client.search(
                collection_name=collection_name.value,
                query_vector=query_vector,
                limit=limit,
                with_payload=True,
            )
        else:
            query_result = self._client.query_points(
                collection_name=collection_name.value,
                query=query_vector,
                limit=limit,
                with_payload=True,
            )
            hits = query_result.points
        results: list[SearchResult] = []
        for hit in hits:
            payload = hit.payload or {}
            document_id = payload.get("document_id")
            chunk_id = payload.get("chunk_id", str(hit.id))
            text = payload.get("text", "")
            if (
                not isinstance(document_id, str)
                or not isinstance(chunk_id, str)
                or not isinstance(text, str)
            ):
                continue
            results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    document_id=DocumentId(document_id),
                    score=float(hit.score),
                    text=text,
                )
            )
        return results

    def delete_collection(self, collection_name: CollectionName) -> None:
        exists = self._client.collection_exists(
            collection_name=collection_name.value
        )
        if not exists:
            return
        self._client.delete_collection(collection_name=collection_name.value)
