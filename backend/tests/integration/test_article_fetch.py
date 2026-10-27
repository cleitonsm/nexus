"""CT-96 (SPEC-20261026-012): leitura de artigo no Qdrant real.

Exige o Qdrant do Compose; nao usa modelos (vetores fixos). Execute dentro do
container do backend.
"""

from __future__ import annotations

import os
import unittest
from uuid import uuid4

from src.domain import AssistantId, CollectionName, DocumentId, VectorChunk

try:
    from src.infrastructure.vector_store import QdrantVectorStoreGateway
except ImportError:  # pragma: no cover
    QdrantVectorStoreGateway = None

ASSISTANT = AssistantId("assistant-article")


def _qdrant():
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


def _chunk(document: str, index: int, article: str | None, **extra) -> VectorChunk:
    return VectorChunk(
        id=f"{document}:{index}",
        document_id=DocumentId(document),
        assistant_id=ASSISTANT,
        chunk_index=index,
        source_name=f"{document}.txt",
        content_hash="hash",
        text=f"{document} trecho {index}",
        vector=[1.0, 0.0, 0.0, 0.0],
        section_path=f"Art. {article}" if article else "",
        legal_article=article,
        **extra,
    )


class ArticleFetchTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        gateway = _qdrant()
        if gateway is None:
            raise unittest.SkipTest("Qdrant indisponivel")
        cls.gateway = gateway
        cls.collection = CollectionName(f"test_article_{uuid4().hex[:12]}")
        gateway.ensure_collection(cls.collection, 4)
        # Fora de ordem de proposito: a leitura precisa ordenar.
        gateway.upsert_chunks(
            cls.collection,
            [
                _chunk("lei", 3, "5"),
                _chunk("lei", 1, "5"),
                _chunk("lei", 2, "5"),
                _chunk("lei", 4, "6"),
                _chunk("lei", 0, None),
                _chunk("restrita", 0, "5", allowed_groups=("juridico",)),
                _chunk("pendente", 0, "5", active=False),
            ],
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.gateway.delete_collection(cls.collection)

    def _fetch(self, article: str, groups: frozenset[str] | None, limit: int = 50):
        return self.gateway.fetch_article(
            self.collection, article, limit, user_groups=groups
        )

    def test_article_comes_in_document_order_with_exact_score(self) -> None:
        results = self._fetch("5", frozenset())
        self.assertEqual([item.chunk_id for item in results], ["lei:1", "lei:2", "lei:3"])
        self.assertEqual([item.chunk_index for item in results], [1, 2, 3])
        self.assertTrue(all(item.score == 1.0 for item in results))

    def test_access_filter_and_inactive_chunks(self) -> None:
        chunk_ids = {item.chunk_id for item in self._fetch("5", frozenset({"juridico"}))}
        self.assertIn("restrita:0", chunk_ids)
        self.assertNotIn("pendente:0", chunk_ids)
        self.assertNotIn("restrita:0", {item.chunk_id for item in self._fetch("5", frozenset())})

    def test_limit_and_missing_collection(self) -> None:
        self.assertEqual(len(self._fetch("5", frozenset(), limit=2)), 2)
        self.assertEqual(
            self.gateway.fetch_article(
                CollectionName(f"test_missing_{uuid4().hex[:8]}"),
                "5",
                10,
                user_groups=frozenset(),
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
