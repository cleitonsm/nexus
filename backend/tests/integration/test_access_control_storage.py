"""SPEC-20261007-004: acesso no Qdrant e no PostgreSQL (CT-28, CT-31).

Exige o Qdrant e o PostgreSQL do Compose. Execute dentro do container do
backend. Cada teste e pulado se o servico correspondente nao responder.
"""

from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.application.services import ContextRetriever, RetrievalSettings
from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    AuditEvent,
    AuditQuery,
    CollectionName,
    Conversation,
    ConversationId,
    Document,
    DocumentId,
    SearchResult,
    SparseVector,
    VectorChunk,
)

try:
    from qdrant_client.http import models

    from src.infrastructure.vector_store import QdrantVectorStoreGateway
except ImportError:  # pragma: no cover
    QdrantVectorStoreGateway = None

VECTOR = [1.0, 0.0, 0.5, 0.25]
SPARSE = SparseVector(indices=(7,), values=(1.0,))
PUBLIC = "doc-publico"
BOARD = "doc-diretoria"
SHARED = "doc-rh-e-diretoria"
LEGACY = "doc-anterior"


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


def _chunk(
    assistant_id: AssistantId,
    document_id: str,
    index: int,
    groups: tuple[str, ...],
) -> VectorChunk:
    return VectorChunk(
        id=f"{document_id}:{index}",
        document_id=DocumentId(document_id),
        assistant_id=assistant_id,
        chunk_index=index,
        source_name=f"{document_id}.md",
        content_hash="hash",
        text=f"trecho {index} de {document_id}",
        vector=VECTOR,
        embedding_model="modelo-teste",
        pipeline_version="3",
        sparse_vector=SPARSE,
        allowed_groups=groups,
    )


class FixedEmbedding:
    model_name = "modelo-teste"
    dimension = 4

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [VECTOR for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return VECTOR


class FixedSparseEmbedding:
    def embed_documents(self, texts: list[str]) -> list[SparseVector]:
        return [SPARSE for _ in texts]

    def embed_query(self, text: str) -> SparseVector:
        return SPARSE


class KeepScoreReranker:
    model_name = "fake-reranker"

    def rerank(self, query: str, candidates: list[SearchResult]) -> list[SearchResult]:
        return list(candidates)


class DocumentRestrictionSearchTestCase(unittest.TestCase):
    """CT-28 (RF-43, RNF-23): o filtro age dentro da consulta ao Qdrant."""

    def setUp(self) -> None:
        gateway = _gateway()
        if gateway is None:
            self.skipTest("Qdrant indisponivel")
        self.gateway = gateway
        self.assistant_id = AssistantId(f"teste-acesso-{uuid4().hex[:12]}")
        self.alias = CollectionName.from_assistant_id(self.assistant_id)
        self.collection = CollectionName.versioned(self.assistant_id, 1)
        gateway.ensure_collection(self.collection, vector_size=4)
        self.addCleanup(gateway.delete_collection, self.collection)
        gateway.point_alias(self.alias, self.collection)
        gateway.upsert_chunks(
            self.collection,
            [
                _chunk(self.assistant_id, PUBLIC, 0, ()),
                _chunk(self.assistant_id, PUBLIC, 1, ()),
                _chunk(self.assistant_id, BOARD, 0, ("diretoria",)),
                _chunk(self.assistant_id, BOARD, 1, ("diretoria",)),
                _chunk(self.assistant_id, SHARED, 0, ("diretoria", "rh")),
            ],
        )

    def _documents(
        self,
        user_groups: frozenset[str] | None,
        sparse: SparseVector = SPARSE,
        **kwargs: object,
    ) -> set[str]:
        hits = self.gateway.hybrid_search(
            self.alias, VECTOR, sparse, 20, user_groups=user_groups, **kwargs
        )
        return {hit.document_id.value for hit in hits}

    def test_user_outside_the_group_never_retrieves_the_restricted_document(self) -> None:
        self.assertEqual(self._documents(frozenset({"financeiro"})), {PUBLIC})
        self.assertEqual(self._documents(frozenset()), {PUBLIC})

    def test_filter_applies_to_the_dense_and_to_the_sparse_prefetch(self) -> None:
        only_dense = self._documents(frozenset({"financeiro"}), sparse=SparseVector())
        self.assertEqual(only_dense, {PUBLIC})

    def test_user_of_the_group_retrieves_the_restricted_document(self) -> None:
        self.assertEqual(
            self._documents(frozenset({"diretoria"})), {PUBLIC, BOARD, SHARED}
        )

    def test_one_group_in_common_is_enough(self) -> None:
        self.assertEqual(
            self._documents(frozenset({"rh", "financeiro"})), {PUBLIC, SHARED}
        )

    def test_group_names_are_matched_exactly(self) -> None:
        self.assertEqual(self._documents(frozenset({"Diretoria", "diret"})), {PUBLIC})

    def test_access_filter_combines_with_the_payload_filter(self) -> None:
        self.assertEqual(
            self._documents(
                frozenset({"financeiro"}), payload_filter={"document_id": BOARD}
            ),
            set(),
        )
        self.assertEqual(
            self._documents(
                frozenset({"diretoria"}), payload_filter={"document_id": BOARD}
            ),
            {BOARD},
        )

    def test_process_without_user_sees_the_whole_base(self) -> None:
        self.assertEqual(self._documents(None), {PUBLIC, BOARD, SHARED})

    def test_restriction_changes_without_reindexing(self) -> None:
        before = self.gateway.count_points(self.collection)
        self.gateway.set_document_groups(
            self.alias, DocumentId(PUBLIC), frozenset({"diretoria"})
        )
        self.assertEqual(self._documents(frozenset({"financeiro"})), set())
        self.gateway.set_document_groups(self.alias, DocumentId(BOARD), frozenset())
        self.assertEqual(self._documents(frozenset({"financeiro"})), {BOARD})
        self.assertEqual(self.gateway.count_points(self.collection), before)

    def test_restriction_on_an_assistant_without_collection_is_not_an_error(self) -> None:
        missing = CollectionName(f"assistant-inexistente-{uuid4().hex[:8]}")
        self.gateway.set_document_groups(
            missing, DocumentId("doc-x"), frozenset({"rh"})
        )
        self.assertFalse(self.gateway.collection_exists(missing))

    def test_chunks_written_before_the_restriction_existed_stay_open(self) -> None:
        self.gateway._client.upsert(  # noqa: SLF001
            collection_name=self.collection.value,
            points=[
                models.PointStruct(
                    id=str(uuid4()),
                    vector={"dense": VECTOR},
                    payload={
                        "chunk_id": f"{LEGACY}:0",
                        "document_id": LEGACY,
                        "text": "trecho gravado na fase 3",
                        "source_name": "antigo.md",
                    },
                )
            ],
            wait=True,
        )
        self.assertIn(LEGACY, self._documents(frozenset({"financeiro"})))

    def test_retriever_returns_nothing_from_the_restricted_document(self) -> None:
        """Sem trecho recuperado, o chat responde com o fallback."""
        self.gateway.set_document_groups(
            self.alias, DocumentId(PUBLIC), frozenset({"diretoria"})
        )
        self.gateway.set_document_groups(
            self.alias, DocumentId(SHARED), frozenset({"diretoria"})
        )
        retriever = ContextRetriever(
            embedding_gateway=FixedEmbedding(),
            sparse_embedding_gateway=FixedSparseEmbedding(),
            vector_store_gateway=self.gateway,
            reranker_gateway=KeepScoreReranker(),
            settings=RetrievalSettings(),
        )
        outside = retriever.search(
            self.assistant_id, "pergunta", user_groups=frozenset({"rh"})
        )
        inside = retriever.search(
            self.assistant_id, "pergunta", user_groups=frozenset({"diretoria"})
        )
        self.assertEqual(outside, [])
        self.assertEqual(
            {hit.document_id.value for hit in inside}, {PUBLIC, BOARD, SHARED}
        )


def _database_session():
    """Sessao no PostgreSQL com as migracoes aplicadas, ou None."""
    try:
        from sqlalchemy import text

        from src.infrastructure.database import SessionLocal, run_migrations

        run_migrations()
        session = SessionLocal()
        session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - banco indisponivel pula o teste
        return None
    return session


class DatabaseTestCase(unittest.TestCase):
    def setUp(self) -> None:
        session = _database_session()
        if session is None:
            self.skipTest("PostgreSQL indisponivel")
        self.session = session
        self.addCleanup(session.close)


class AuditTrailStorageTestCase(DatabaseTestCase):
    """CT-31 (RF-45, RN-25): eventos gravados e nunca alterados."""

    def setUp(self) -> None:
        super().setUp()
        from src.infrastructure.database import PostgresAuditLogRepository

        self.repository = PostgresAuditLogRepository(session=self.session)
        # Os eventos nao podem ser apagados depois; cada execucao usa
        # identificadores proprios para nao enxergar as anteriores.
        self.run_id = uuid4().hex[:12]
        self.user_id = f"teste-{self.run_id}"
        self.assistant_id = f"assistant-{self.run_id}"
        self.base_time = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)

    def _append(self, index: int, action: str, **details: object) -> AuditEvent:
        return self.repository.append(
            AuditEvent(
                id=f"{self.run_id}-{index}",
                user_id=self.user_id,
                action=action,
                resource_type="assistant",
                resource_id=self.assistant_id,
                details=details,
                occurred_at=self.base_time + timedelta(minutes=index),
            )
        )

    def test_events_round_trip_most_recent_first(self) -> None:
        self._append(1, "chat.question", assistant_id=self.assistant_id)
        self._append(
            2,
            "document.groups_changed",
            assistant_id=self.assistant_id,
            before=[],
            after=["diretoria"],
        )
        self.session.expire_all()
        events = self.repository.list_events(AuditQuery(user_id=self.user_id))
        self.assertEqual(
            [event.action for event in events],
            ["document.groups_changed", "chat.question"],
        )
        self.assertEqual(events[0].details["after"], ["diretoria"])
        self.assertEqual(events[0].occurred_at, self.base_time + timedelta(minutes=2))

    def test_events_are_filtered_by_action_assistant_period_and_page(self) -> None:
        self._append(1, "chat.question", assistant_id=self.assistant_id)
        self._append(2, "chat.question", assistant_id="outro-assistente")
        self._append(3, "auth.session_started")

        def ids(**filters: object) -> list[str]:
            query = AuditQuery(user_id=self.user_id, **filters)
            return [event.id.rsplit("-", 1)[1] for event in self.repository.list_events(query)]

        self.assertEqual(ids(action="chat.question"), ["2", "1"])
        self.assertEqual(ids(assistant_id=self.assistant_id), ["1"])
        self.assertEqual(
            ids(
                occurred_from=self.base_time + timedelta(minutes=2),
                occurred_to=self.base_time + timedelta(minutes=2),
            ),
            ["2"],
        )
        self.assertEqual(ids(limit=1), ["3"])
        self.assertEqual(ids(limit=1, offset=1), ["2"])

    def _refused(self, statement: str, **parameters: object) -> None:
        from sqlalchemy import text
        from sqlalchemy.exc import DBAPIError

        try:
            with self.assertRaises(DBAPIError):
                self.session.execute(text(statement), parameters)
                self.session.commit()
        finally:
            self.session.rollback()

    def test_database_refuses_update_delete_and_truncate(self) -> None:
        event = self._append(1, "chat.question")
        self._refused("UPDATE audit_events SET action = 'x' WHERE id = :id", id=event.id)
        self._refused("DELETE FROM audit_events WHERE id = :id", id=event.id)
        # So chega aqui se o gatilho recusou as duas anteriores: sem ele, o
        # TRUNCATE apagaria a trilha inteira do ambiente.
        self._refused("TRUNCATE audit_events")
        (stored,) = self.repository.list_events(AuditQuery(user_id=self.user_id))
        self.assertEqual(stored.action, "chat.question")

    def test_retention_purge_removes_only_events_older_than_the_cutoff(self) -> None:
        """D6: so o repositorio de retencao apaga, e so antes do corte.

        Os eventos deste teste sao do ano 2000, para que o corte nunca alcance
        eventos reais do ambiente.
        """
        from src.infrastructure.database import PostgresAuditRetentionRepository

        old = self.repository.append(
            AuditEvent(
                id=f"{self.run_id}-antigo",
                user_id=self.user_id,
                action="chat.question",
                resource_type="assistant",
                occurred_at=datetime(2000, 1, 1, tzinfo=UTC),
            )
        )
        kept = self.repository.append(
            AuditEvent(
                id=f"{self.run_id}-mantido",
                user_id=self.user_id,
                action="chat.question",
                resource_type="assistant",
                occurred_at=datetime(2000, 1, 3, tzinfo=UTC),
            )
        )
        removed = PostgresAuditRetentionRepository(session=self.session).purge_older_than(
            datetime(2000, 1, 2, tzinfo=UTC)
        )
        self.assertGreaterEqual(removed, 1)
        remaining = {
            event.id
            for event in self.repository.list_events(AuditQuery(user_id=self.user_id))
        }
        self.assertNotIn(old.id, remaining)
        self.assertIn(kept.id, remaining)
        # A permissao vale so na transacao da limpeza.
        self._refused("DELETE FROM audit_events WHERE id = :id", id=kept.id)

    def test_repository_offers_no_update_or_delete(self) -> None:
        operations = {
            name for name in dir(self.repository) if not name.startswith("_")
        }
        self.assertEqual(operations, {"append", "list_events"})


class PermissionStorageTestCase(DatabaseTestCase):
    """Migracao 0004: grupos de assistentes e de documentos e dono da conversa."""

    def setUp(self) -> None:
        super().setUp()
        from src.infrastructure.database import (
            PostgresAssistantPermissionRepository,
            PostgresAssistantRepository,
            PostgresConversationRepository,
            PostgresDocumentRepository,
        )

        self.assistants = PostgresAssistantRepository(session=self.session)
        self.documents = PostgresDocumentRepository(session=self.session)
        self.conversations = PostgresConversationRepository(session=self.session)
        self.permissions = PostgresAssistantPermissionRepository(session=self.session)
        self.assistant_id = AssistantId(f"teste-acesso-{uuid4().hex[:12]}")
        self.assistants.save(
            Assistant(id=self.assistant_id, name=AssistantName("Acesso"))
        )
        self.addCleanup(self.assistants.delete, self.assistant_id)

    def _document(self, name: str) -> DocumentId:
        document_id = DocumentId(f"{name}-{uuid4().hex[:12]}")
        self.documents.save(
            Document(
                id=document_id,
                assistant_id=self.assistant_id,
                source_name=f"{name}.md",
                content_hash="hash",
            )
        )
        return document_id

    def test_new_assistant_has_no_group(self) -> None:
        self.assertEqual(
            self.permissions.get_assistant_groups(self.assistant_id), frozenset()
        )
        self.assertNotIn(
            self.assistant_id.value, self.permissions.list_assistant_groups()
        )

    def test_assistant_groups_are_replaced_as_a_whole(self) -> None:
        self.permissions.set_assistant_groups(
            self.assistant_id, frozenset({"rh", "financeiro"})
        )
        self.permissions.set_assistant_groups(
            self.assistant_id, frozenset({"rh", "diretoria"})
        )
        self.session.expire_all()
        expected = frozenset({"rh", "diretoria"})
        self.assertEqual(
            self.permissions.get_assistant_groups(self.assistant_id), expected
        )
        self.assertEqual(
            self.permissions.list_assistant_groups()[self.assistant_id.value],
            expected,
        )
        self.permissions.set_assistant_groups(self.assistant_id, frozenset())
        self.assertEqual(
            self.permissions.get_assistant_groups(self.assistant_id), frozenset()
        )

    def test_document_groups_are_listed_by_assistant(self) -> None:
        restricted = self._document("restrito")
        free = self._document("livre")
        self.permissions.set_document_groups(restricted, frozenset({"diretoria"}))
        self.session.expire_all()
        self.assertEqual(
            self.permissions.get_document_groups(restricted), frozenset({"diretoria"})
        )
        self.assertEqual(self.permissions.get_document_groups(free), frozenset())
        self.assertEqual(
            self.permissions.list_document_groups(self.assistant_id),
            {restricted.value: frozenset({"diretoria"})},
        )
        self.assertEqual(self.documents.get_by_id(free).source_name, "livre.md")
        self.assertIsNone(self.documents.get_by_id(DocumentId("nao-existe")))

    def test_groups_are_removed_with_the_assistant(self) -> None:
        document_id = self._document("restrito")
        self.permissions.set_assistant_groups(self.assistant_id, frozenset({"rh"}))
        self.permissions.set_document_groups(document_id, frozenset({"rh"}))
        self.assistants.delete(self.assistant_id)
        self.session.expire_all()
        self.assertEqual(
            self.permissions.get_assistant_groups(self.assistant_id), frozenset()
        )
        self.assertEqual(self.permissions.get_document_groups(document_id), frozenset())

    def test_conversations_are_listed_only_for_their_owner(self) -> None:
        owned = ConversationId(str(uuid4()))
        foreign = ConversationId(str(uuid4()))
        archived = ConversationId(str(uuid4()))
        for conversation_id, owner in (
            (owned, "ana"),
            (foreign, "bruno"),
            (archived, None),
        ):
            self.conversations.save(
                Conversation(
                    id=conversation_id,
                    assistant_id=self.assistant_id,
                    owner_user_id=owner,
                )
            )
        self.session.expire_all()
        listed = self.conversations.list_by_assistant(self.assistant_id, "ana")
        self.assertEqual([item.id for item in listed], [owned])
        self.assertEqual(self.conversations.get_by_id(owned).owner_user_id, "ana")
        self.assertIsNone(self.conversations.get_by_id(archived).owner_user_id)


if __name__ == "__main__":
    unittest.main()
