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
        if self.collection_exists(collection_name):
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
                    payload=_payload(chunk),
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
        if not self.collection_exists(collection_name):
            return
        self._client.delete_collection(collection_name=collection_name.value)

    def collection_exists(self, collection_name: CollectionName) -> bool:
        """Considera apenas collections fisicas; um alias nao conta."""
        existing = self._client.get_collections().collections
        return any(item.name == collection_name.value for item in existing)

    def count_points(self, collection_name: CollectionName) -> int:
        result = self._client.count(
            collection_name=collection_name.value,
            exact=True,
        )
        return int(result.count)

    def resolve_alias(self, alias: CollectionName) -> CollectionName | None:
        for item in self._client.get_aliases().aliases:
            if item.alias_name == alias.value:
                return CollectionName(item.collection_name)
        return None

    def point_alias(
        self,
        alias: CollectionName,
        collection_name: CollectionName,
    ) -> None:
        """Remove o alias anterior e cria o novo na mesma operacao atomica."""
        operations: list[object] = []
        if self.resolve_alias(alias) is not None:
            operations.append(
                models.DeleteAliasOperation(
                    delete_alias=models.DeleteAlias(alias_name=alias.value)
                )
            )
        operations.append(
            models.CreateAliasOperation(
                create_alias=models.CreateAlias(
                    collection_name=collection_name.value,
                    alias_name=alias.value,
                )
            )
        )
        self._client.update_collection_aliases(
            change_aliases_operations=operations
        )


def _payload(chunk: VectorChunk) -> dict[str, object]:
    return {
        "chunk_id": chunk.id,
        "assistant_id": chunk.assistant_id.value,
        "document_id": chunk.document_id.value,
        "chunk_index": chunk.chunk_index,
        "source_name": chunk.source_name,
        "content_hash": chunk.content_hash,
        "text": chunk.text,
        "section_path": chunk.section_path,
        "page": chunk.page,
        "embedding_model": chunk.embedding_model,
        "pipeline_version": chunk.pipeline_version,
    }
