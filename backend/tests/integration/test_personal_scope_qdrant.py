"""CT-148 (SPEC-018): escopo pessoal na busca do Qdrant (RN-59, ADR 0014).

Usa uma versao fisica temporaria da collection do resumidor, com vetores de
4 dimensoes escritos a mao (sem modelos). Exige o Qdrant do Compose; sem ele, o
teste e pulado. Execute dentro do container do backend.
"""

from __future__ import annotations

import os
import random
import unittest

from src.domain import (
    SUMMARIZER_ASSISTANT_ID,
    SUMMARIZER_COLLECTION,
    CollectionName,
    ConversationId,
    DocumentId,
    PersonalScope,
    SparseVector,
    VectorChunk,
)

try:
    from src.infrastructure.vector_store import QdrantVectorStoreGateway
except ImportError:  # pragma: no cover
    QdrantVectorStoreGateway = None  # type: ignore[assignment,misc]

VECTOR = [1.0, 0.0, 0.0, 0.0]
EMPTY = SparseVector(indices=(), values=())
ANA_C1 = PersonalScope(owner_user_id="ana", conversation_id=ConversationId("c1"))
ANA_C2 = PersonalScope(owner_user_id="ana", conversation_id=ConversationId("c2"))
BRUNO_C1 = PersonalScope(owner_user_id="bruno", conversation_id=ConversationId("c1"))


def _gateway():
    if QdrantVectorStoreGateway is None:
        return None
    gateway = QdrantVectorStoreGateway(
        url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
        api_key=os.getenv("QDRANT_API_KEY", "") or None,
    )
    try:
        gateway.collection_exists(CollectionName("nexus-connectivity-check"))
    except Exception:  # noqa: BLE001 - sem Qdrant, o teste e pulado
        return None
    return gateway


def _chunk(document: str, owner: str, conversation: str, index: int = 0) -> VectorChunk:
    return VectorChunk(
        id=f"{document}:{index}",
        document_id=DocumentId(document),
        assistant_id=SUMMARIZER_ASSISTANT_ID,
        chunk_index=index,
        source_name=f"{document}.pdf",
        content_hash="h",
        text=f"trecho ficticio de {document}",
        vector=VECTOR,
        owner_user_id=owner,
        conversation_id=conversation,
    )


class PersonalScopeQdrantTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        gateway = _gateway()
        if gateway is None:
            raise unittest.SkipTest("Qdrant indisponivel")
        cls.gateway = gateway
        cls.collection = CollectionName(
            f"{SUMMARIZER_COLLECTION.value}-v{random.randint(90_000, 99_999)}"
        )
        gateway.ensure_collection(cls.collection, vector_size=4)
        gateway.upsert_chunks(
            cls.collection,
            [
                _chunk("doc-ana-c1", "ana", "c1"),
                _chunk("doc-ana-c1", "ana", "c1", index=1),
                _chunk("doc-ana-c2", "ana", "c2"),
                _chunk("doc-bruno-c1", "bruno", "c1"),
            ],
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.gateway.delete_collection(cls.collection)

    def search(self, scope: PersonalScope | None, *, groups=frozenset()):
        return self.gateway.hybrid_search(
            self.collection, VECTOR, EMPTY, 10, user_groups=groups, personal_scope=scope
        )

    def test_scope_returns_only_the_owner_and_conversation(self) -> None:
        cases = (
            (ANA_C1, {"doc-ana-c1"}),
            (ANA_C2, {"doc-ana-c2"}),
            (BRUNO_C1, {"doc-bruno-c1"}),
            (PersonalScope(owner_user_id="carla", conversation_id=ConversationId("c1")), set()),
        )
        for scope, expected in cases:
            with self.subTest(scope=scope):
                found = {item.document_id.value for item in self.search(scope)}
                self.assertEqual(found, expected)

    def test_without_scope_the_summarizer_collection_is_not_queried(self) -> None:
        """Falha fechada: nunca uma busca sem filtro de dono e conversa."""
        with self.assertRaises(ValueError):
            self.search(None)
        with self.assertRaises(ValueError):
            self.gateway.fetch_article(self.collection, "5", 10, user_groups=frozenset())

    def test_group_and_active_filters_still_apply(self) -> None:
        """Os filtros de sempre continuam: trecho inativo nao volta."""
        self.gateway.set_document_active(self.collection, DocumentId("doc-ana-c2"), False)
        self.addCleanup(
            self.gateway.set_document_active, self.collection, DocumentId("doc-ana-c2"), True
        )
        self.assertEqual(self.search(ANA_C2), [])
        # Pontos pessoais nao tem restricao de grupo: qualquer conjunto passa.
        self.assertTrue(self.search(ANA_C1, groups=frozenset({"rh"})))


if __name__ == "__main__":
    unittest.main()
