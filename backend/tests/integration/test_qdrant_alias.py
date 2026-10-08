"""CT-12 (SPEC-20261007-002): troca de alias sob consultas concorrentes.

Exige o Qdrant do Compose. Execute dentro do container do backend.
"""

from __future__ import annotations

import os
import threading
import unittest
from uuid import uuid4

from src.domain import (
    AssistantId,
    CollectionName,
    DocumentId,
    SearchResult,
    SparseVector,
    VectorChunk,
)

try:
    from src.infrastructure.vector_store import QdrantVectorStoreGateway
except ImportError:  # pragma: no cover
    QdrantVectorStoreGateway = None

SWAPS = 20
SEARCH_THREADS = 4


def _gateway() -> "QdrantVectorStoreGateway | None":
    if QdrantVectorStoreGateway is None:
        return None
    gateway = QdrantVectorStoreGateway(
        url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
        api_key=os.getenv("QDRANT_API_KEY", "") or None,
    )
    try:
        gateway.collection_exists(CollectionName("nexus-connectivity-check"))
    except Exception:  # noqa: BLE001 - qualquer falha de conexao pula o teste
        return None
    return gateway


def _chunk(assistant_id: AssistantId, index: int, marker: str) -> VectorChunk:
    return VectorChunk(
        id=f"doc-{marker}:{index}",
        document_id=DocumentId(f"doc-{marker}"),
        assistant_id=assistant_id,
        chunk_index=index,
        source_name=f"{marker}.md",
        content_hash="hash",
        text=f"trecho {index} da versao {marker}",
        vector=[1.0, float(index), 0.5, 0.25],
        section_path="Secao",
        page=None,
        embedding_model="modelo-teste",
        pipeline_version="3",
    )


def _search(
    gateway: "QdrantVectorStoreGateway",
    collection: CollectionName,
    vector: list[float],
    limit: int,
) -> list[SearchResult]:
    """So a parte densa: o alias independe do vetor esparso."""
    return gateway.hybrid_search(
        collection, vector, SparseVector(), limit, user_groups=None
    )


class QdrantAliasTestCase(unittest.TestCase):
    def setUp(self) -> None:
        gateway = _gateway()
        if gateway is None:
            self.skipTest("Qdrant indisponivel")
        self.gateway = gateway
        self.assistant_id = AssistantId(f"teste-alias-{uuid4().hex[:12]}")
        self.alias = CollectionName.from_assistant_id(self.assistant_id)
        self.first = CollectionName.versioned(self.assistant_id, 1)
        self.second = CollectionName.versioned(self.assistant_id, 2)
        for collection, marker in ((self.first, "v1"), (self.second, "v2")):
            self.gateway.ensure_collection(collection, vector_size=4)
            self.gateway.upsert_chunks(
                collection,
                [_chunk(self.assistant_id, index, marker) for index in range(5)],
            )
        self.addCleanup(self.gateway.delete_collection, self.first)
        self.addCleanup(self.gateway.delete_collection, self.second)

    def test_alias_resolution_count_and_physical_existence(self) -> None:
        self.assertIsNone(self.gateway.resolve_alias(self.alias))
        self.gateway.point_alias(self.alias, self.first)
        self.assertEqual(self.gateway.resolve_alias(self.alias), self.first)
        self.assertEqual(self.gateway.count_points(self.first), 5)
        self.assertTrue(self.gateway.collection_exists(self.first))
        self.assertFalse(self.gateway.collection_exists(self.alias))

    def test_payload_carries_phase_two_metadata(self) -> None:
        self.gateway.point_alias(self.alias, self.first)
        hits = _search(self.gateway, self.alias, [1.0, 0.0, 0.5, 0.25], 1)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].document_id.value, "doc-v1")

    def test_alias_swap_during_concurrent_searches_raises_no_error(self) -> None:
        """CT-12 / RNF-18: consultas continuam durante a troca."""
        self.gateway.point_alias(self.alias, self.first)
        errors: list[BaseException] = []
        empty_results: list[int] = []
        stop = threading.Event()

        def _search() -> None:
            while not stop.is_set():
                try:
                    hits = _search(
                        self.gateway, self.alias, [1.0, 1.0, 0.5, 0.25], 3
                    )
                    if not hits:
                        empty_results.append(1)
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)

        threads = [threading.Thread(target=_search) for _ in range(SEARCH_THREADS)]
        for thread in threads:
            thread.start()
        try:
            for swap in range(SWAPS):
                target = self.second if swap % 2 == 0 else self.first
                self.gateway.point_alias(self.alias, target)
        finally:
            stop.set()
            for thread in threads:
                thread.join(timeout=30)

        self.assertEqual(errors, [])
        self.assertEqual(empty_results, [])
        self.assertEqual(self.gateway.resolve_alias(self.alias), self.first)

    def test_deleting_previous_version_keeps_alias_working(self) -> None:
        self.gateway.point_alias(self.alias, self.first)
        self.gateway.point_alias(self.alias, self.second)
        self.gateway.delete_collection(self.first)
        hits = _search(self.gateway, self.alias, [1.0, 0.0, 0.5, 0.25], 1)
        self.assertEqual(hits[0].document_id.value, "doc-v2")


if __name__ == "__main__":
    unittest.main()
