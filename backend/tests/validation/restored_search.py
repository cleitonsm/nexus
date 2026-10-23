"""CT-47: depois da restauracao, a busca encontra os documentos restaurados.

Executado por ``scripts/validation/backup-restore.sh`` dentro do contêiner do
backend do ambiente limpo, com ``./backend/tests`` montado em ``/app/tests``:

    python -m tests.validation.restored_search

Para cada assistente, pega um trecho ativo de ate tres documentos indexados,
busca pelas primeiras palavras dele e exige que o proprio documento volte entre
os candidatos. Usa a mesma busca do chat (``ContextRetriever.search``), sem
filtro de grupos, como a avaliacao. Nao imprime texto de documento: so ids.

Codigo de saida: 0 todas as buscas acharam o documento; 1 alguma falhou ou
nao havia documento indexado; 2 erro de execucao.
"""

from __future__ import annotations

import json
import os
import sys

from qdrant_client import QdrantClient, models

from src.application.services import ContextRetriever
from src.domain import CollectionName, Document, DocumentStatus
from src.infrastructure.composition import (
    build_embedding_gateway,
    build_reranker_gateway,
    build_sparse_embedding_gateway,
    retrieval_settings,
)
from src.infrastructure.database import (
    PostgresAssistantRepository,
    PostgresDocumentRepository,
    SessionLocal,
)
from src.infrastructure.vector_store import QdrantVectorStoreGateway

DOCUMENTS_PER_ASSISTANT = 3
QUERY_WORDS = 12


def _query_for(client: QdrantClient, collection: str, document_id: str) -> str | None:
    points, _ = client.scroll(
        collection_name=collection,
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id", match=models.MatchValue(value=document_id)
                )
            ],
            must_not=[
                models.FieldCondition(key="active", match=models.MatchValue(value=False))
            ],
        ),
        limit=1,
        with_payload=True,
    )
    if not points:
        return None
    words = str((points[0].payload or {}).get("text", "")).split()
    return " ".join(words[:QUERY_WORDS]) or None


def _check(retriever: ContextRetriever, client: QdrantClient, document: Document) -> dict:
    collection = CollectionName.from_assistant_id(document.assistant_id).value
    query = _query_for(client, collection, document.id.value)
    if query is None:
        return {"document_id": document.id.value, "found": False, "reason": "sem trecho ativo"}
    results = retriever.search(document.assistant_id, query, user_groups=None)
    found = any(item.document_id == document.id for item in results)
    return {"document_id": document.id.value, "found": found, "candidates": len(results)}


def main() -> int:
    qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
    api_key = os.getenv("QDRANT_API_KEY", "") or None
    client = QdrantClient(url=qdrant_url, api_key=api_key)
    retriever = ContextRetriever(
        embedding_gateway=build_embedding_gateway(),
        sparse_embedding_gateway=build_sparse_embedding_gateway(),
        vector_store_gateway=QdrantVectorStoreGateway(url=qdrant_url, api_key=api_key),
        reranker_gateway=build_reranker_gateway(),
        settings=retrieval_settings(),
    )
    checks: list[dict] = []
    with SessionLocal() as session:
        documents = PostgresDocumentRepository(session=session)
        for assistant in PostgresAssistantRepository(session=session).list_all():
            indexed = [
                item
                for item in documents.list_by_assistant(assistant.id)
                if item.status is DocumentStatus.INDEXED
            ][:DOCUMENTS_PER_ASSISTANT]
            checks.extend(_check(retriever, client, item) for item in indexed)
    sys.stdout.write(json.dumps({"checks": checks}, ensure_ascii=False, indent=2) + "\n")
    if not checks:
        sys.stderr.write("nenhum documento indexado no backup restaurado\n")
        return 1
    return 0 if all(item["found"] for item in checks) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - erro de execucao vira codigo 2
        sys.stderr.write(f"erro: {type(exc).__name__}\n")
        sys.exit(2)
