from __future__ import annotations

import logging
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from src.domain import (
    CollectionName,
    DocumentId,
    IndexOutdatedError,
    SearchResult,
    SparseVector,
    VectorChunk,
)

DENSE_VECTOR = "dense"
SPARSE_VECTOR = "sparse"
# Grupos a que o documento do trecho esta restrito (RF-43). Ausente ou vazio:
# o trecho segue o acesso do assistente.
ALLOWED_GROUPS = "allowed_groups"
DOCUMENT_ID = "document_id"
# Falso enquanto o documento esta em processamento (RN-27, RN-28). Trechos
# gravados antes da SPEC-005 nao tem o campo e contam como ativos.
ACTIVE = "active"
_NOT_FOUND = 404

logger = logging.getLogger(__name__)


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
            vectors_config={
                DENSE_VECTOR: models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                )
            },
            # O IDF do BM25 e calculado pelo Qdrant sobre a collection.
            sparse_vectors_config={
                SPARSE_VECTOR: models.SparseVectorParams(
                    modifier=models.Modifier.IDF,
                )
            },
        )
        self._ensure_group_index(collection_name)

    def _ensure_group_index(self, collection_name: CollectionName) -> None:
        """Indice de payload do filtro de acesso; cria-lo de novo nao tem efeito."""
        self._client.create_payload_index(
            collection_name=collection_name.value,
            field_name=ALLOWED_GROUPS,
            field_schema=models.PayloadSchemaType.KEYWORD,
            wait=True,
        )
        self._ensure_lifecycle_indexes(collection_name)

    def _ensure_lifecycle_indexes(self, collection_name: CollectionName) -> None:
        """Indices dos filtros por documento e por trecho ativo (SPEC-005)."""
        for field_name, schema in (
            (DOCUMENT_ID, models.PayloadSchemaType.KEYWORD),
            (ACTIVE, models.PayloadSchemaType.BOOL),
        ):
            self._client.create_payload_index(
                collection_name=collection_name.value,
                field_name=field_name,
                field_schema=schema,
                wait=True,
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
                    vector=_vectors(chunk),
                    payload=_payload(chunk),
                )
                for chunk in chunks
            ],
            wait=True,
        )

    def hybrid_search(
        self,
        collection_name: CollectionName,
        dense_vector: list[float],
        sparse_vector: SparseVector,
        limit: int,
        payload_filter: dict[str, str] | None = None,
        *,
        user_groups: frozenset[str] | None,
    ) -> list[SearchResult]:
        """Pre-busca densa e esparsa, fundidas por RRF na Query API (RF-33).

        O filtro de acesso entra em cada pre-busca: um trecho restrito a
        grupos que o usuario nao tem nunca chega a ser candidato (RNF-23).
        """
        if limit <= 0:
            return []
        query_filter = _filter(payload_filter, user_groups)
        prefetch = [
            models.Prefetch(
                query=dense_vector,
                using=DENSE_VECTOR,
                limit=limit,
                filter=query_filter,
            )
        ]
        if not sparse_vector.is_empty:
            prefetch.append(
                models.Prefetch(
                    query=_sparse(sparse_vector),
                    using=SPARSE_VECTOR,
                    limit=limit,
                    filter=query_filter,
                )
            )
        try:
            response = self._client.query_points(
                collection_name=collection_name.value,
                prefetch=prefetch,
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=limit,
                with_payload=True,
            )
        except UnexpectedResponse as exc:
            if exc.status_code == _NOT_FOUND:
                return []
            if self._has_hybrid_vectors(collection_name):
                raise
            response = self._legacy_dense_search(
                collection_name, dense_vector, limit, query_filter
            )
        return [
            result
            for result in (_to_result(point) for point in response.points)
            if result is not None
        ]

    def _legacy_dense_search(
        self,
        collection_name: CollectionName,
        dense_vector: list[float],
        limit: int,
        query_filter: models.Filter,
    ) -> models.QueryResponse:
        """Collection anterior a SPEC-003 (vetor sem nome): busca so densa.

        Mantem o chat no ar ate a reindexacao; termos exatos so voltam a ser
        encontrados depois dela.
        """
        logger.warning(
            "vector_store.legacy_dense_search",
            extra={"collection": collection_name.value},
        )
        try:
            return self._client.query_points(
                collection_name=collection_name.value,
                query=dense_vector,
                limit=limit,
                query_filter=query_filter,
                with_payload=True,
            )
        except UnexpectedResponse as exc:
            raise IndexOutdatedError(
                "the assistant index is incompatible with the current "
                "embedding model; reindex it."
            ) from exc

    def _has_hybrid_vectors(self, collection_name: CollectionName) -> bool:
        params = self._client.get_collection(collection_name.value).config.params
        dense = params.vectors
        sparse = params.sparse_vectors or {}
        return (
            isinstance(dense, dict)
            and DENSE_VECTOR in dense
            and SPARSE_VECTOR in sparse
        )

    def set_document_groups(
        self,
        collection_name: CollectionName,
        document_id: DocumentId,
        groups: frozenset[str],
    ) -> None:
        """Regrava ``allowed_groups`` em todos os trechos do documento."""
        # O indice e criado na collection fisica; o nome recebido e o alias.
        target = self.resolve_alias(collection_name) or collection_name
        try:
            self._ensure_group_index(target)
            self._client.set_payload(
                collection_name=target.value,
                payload={ALLOWED_GROUPS: sorted(groups)},
                points=_document_filter(document_id),
                wait=True,
            )
        except UnexpectedResponse as exc:
            if exc.status_code != _NOT_FOUND:
                raise
            # Assistente ainda sem collection: nao ha trecho para regravar.

    def delete_by_document(
        self,
        collection_name: CollectionName,
        document_id: DocumentId,
    ) -> None:
        """Remove os trechos do documento pelo filtro de ``document_id``."""
        try:
            self._client.delete(
                collection_name=collection_name.value,
                points_selector=models.FilterSelector(
                    filter=_document_filter(document_id)
                ),
                wait=True,
            )
        except UnexpectedResponse as exc:
            if exc.status_code != _NOT_FOUND:
                raise
            # Assistente ainda sem collection: nao ha trecho para remover.

    def set_document_active(
        self,
        collection_name: CollectionName,
        document_id: DocumentId,
        active: bool,
    ) -> None:
        """Inclui (ou retira) das buscas todos os trechos do documento."""
        target = self.resolve_alias(collection_name) or collection_name
        self._ensure_lifecycle_indexes(target)
        self._client.set_payload(
            collection_name=target.value,
            payload={ACTIVE: active},
            points=_document_filter(document_id),
            wait=True,
        )

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


def _vectors(chunk: VectorChunk) -> dict[str, object]:
    vectors: dict[str, object] = {DENSE_VECTOR: chunk.vector}
    if chunk.sparse_vector is not None and not chunk.sparse_vector.is_empty:
        vectors[SPARSE_VECTOR] = _sparse(chunk.sparse_vector)
    return vectors


def _sparse(vector: SparseVector) -> models.SparseVector:
    return models.SparseVector(
        indices=list(vector.indices),
        values=list(vector.values),
    )


def _filter(
    payload_filter: dict[str, str] | None,
    user_groups: frozenset[str] | None,
) -> models.Filter:
    """Igualdade de campos, trechos ativos (RN-27) e, com usuario, o acesso (RF-43)."""
    must: list[object] = [
        models.FieldCondition(key=key, match=models.MatchValue(value=value))
        for key, value in (payload_filter or {}).items()
    ]
    if user_groups is not None:
        must.append(_access_filter(user_groups))
    # ``must_not`` em vez de ``active = true``: trechos sem o campo, gravados
    # antes da SPEC-005, continuam nas buscas.
    inactive = models.FieldCondition(key=ACTIVE, match=models.MatchValue(value=False))
    return models.Filter(must=must or None, must_not=[inactive])


def _document_filter(document_id: DocumentId) -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(
                key=DOCUMENT_ID,
                match=models.MatchValue(value=document_id.value),
            )
        ]
    )


def _access_filter(user_groups: frozenset[str]) -> models.Filter:
    """Trecho sem restricao, ou restrito a algum grupo do usuario.

    ``is_empty`` cobre campo ausente, nulo e lista vazia; por isso os trechos
    gravados antes da SPEC-004 continuam sem restricao.
    """
    unrestricted = models.IsEmptyCondition(
        is_empty=models.PayloadField(key=ALLOWED_GROUPS)
    )
    conditions: list[object] = [unrestricted]
    if user_groups:
        conditions.append(
            models.FieldCondition(
                key=ALLOWED_GROUPS,
                match=models.MatchAny(any=sorted(user_groups)),
            )
        )
    return models.Filter(should=conditions)


def _to_result(point: models.ScoredPoint) -> SearchResult | None:
    payload = point.payload or {}
    document_id = payload.get("document_id")
    chunk_id = payload.get("chunk_id", str(point.id))
    text = payload.get("text", "")
    if (
        not isinstance(document_id, str)
        or not isinstance(chunk_id, str)
        or not isinstance(text, str)
    ):
        return None
    page = payload.get("page")
    return SearchResult(
        chunk_id=chunk_id,
        document_id=DocumentId(document_id),
        score=float(point.score),
        text=text,
        source_name=str(payload.get("source_name") or ""),
        section_path=str(payload.get("section_path") or ""),
        page=page if isinstance(page, int) and page >= 1 else None,
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
        ALLOWED_GROUPS: list(chunk.allowed_groups),
        ACTIVE: chunk.active,
    }
