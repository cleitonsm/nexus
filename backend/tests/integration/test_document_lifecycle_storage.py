"""SPEC-20261007-005: fila no PostgreSQL e ciclo de vida no Qdrant (CT-37, CT-38).

Exige o PostgreSQL e o Qdrant do Compose. Execute dentro do container do
backend. Cada teste e pulado se o servico correspondente nao responder.
"""

from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    CollectionName,
    Document,
    DocumentId,
    DocumentStatus,
    IngestionJob,
    IngestionJobStatus,
    ReindexJob,
    SparseVector,
    VectorChunk,
)

try:
    from src.infrastructure.vector_store import QdrantVectorStoreGateway
except ImportError:  # pragma: no cover
    QdrantVectorStoreGateway = None

VECTOR = [1.0, 0.0, 0.5, 0.25]
SPARSE = SparseVector(indices=(7,), values=(1.0,))


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


class IngestionQueueStorageTestCase(unittest.TestCase):
    """CT-37: reserva sem disputa, estado gravado com o job, reindexacao (D8)."""

    def setUp(self) -> None:
        session = _database_session()
        if session is None:
            self.skipTest("PostgreSQL indisponivel")
        from src.infrastructure.database import (
            PostgresAssistantRepository,
            PostgresDocumentRepository,
            PostgresIngestionJobQueue,
            PostgresReindexJobRepository,
            SessionLocal,
        )

        self.session = session
        self.addCleanup(session.close)
        self.other_session = SessionLocal()
        self.addCleanup(self.other_session.close)
        self.assistants = PostgresAssistantRepository(session=session)
        self.documents = PostgresDocumentRepository(session=session)
        self.queue = PostgresIngestionJobQueue(session=session)
        self.other_queue = PostgresIngestionJobQueue(session=self.other_session)
        self.reindex_jobs = PostgresReindexJobRepository(session=session)
        self.assistant_id = AssistantId(f"teste-fila-{uuid4().hex[:12]}")
        self.assistants.save(
            Assistant(id=self.assistant_id, name=AssistantName("Teste fila"))
        )
        self.addCleanup(self.assistants.delete, self.assistant_id)
        # Jobs de outros testes nao podem ser reservados aqui.
        self.now = datetime(2000, 1, 1, tzinfo=UTC)

    def _pending_document(self, suffix: str = "") -> Document:
        return self.documents.save(
            Document(
                id=DocumentId(f"{self.assistant_id.value}-doc{suffix}"),
                assistant_id=self.assistant_id,
                source_name="politica.md",
                content_hash=f"hash-{uuid4().hex}",
                status=DocumentStatus.PENDING,
                storage_key="a/b.md",
                size_bytes=10,
                uploaded_by="teste",
            )
        )

    def _job(self, document: Document) -> IngestionJob:
        return self.queue.enqueue(
            IngestionJob(
                id=str(uuid4()),
                document_id=document.id,
                available_at=self.now,
                created_at=self.now,
            )
        )

    def test_two_consumers_never_reserve_the_same_job(self) -> None:
        from sqlalchemy import select

        from src.infrastructure.database import IngestionJobModel

        document = self._pending_document()
        job = self._job(document)
        # O primeiro consumidor trava a linha sem concluir a transacao.
        locked = self.session.scalars(
            select(IngestionJobModel)
            .where(IngestionJobModel.id == job.id)
            .with_for_update()
        ).one()
        self.assertEqual(locked.status, "pendente")
        self.assertIsNone(self.other_queue.reserve_next(self.now))
        self.session.rollback()

        reserved = self.other_queue.reserve_next(self.now)
        self.assertEqual(reserved.id, job.id)
        self.assertEqual(reserved.attempts, 1)
        self.assertIsNone(self.queue.reserve_next(self.now))

    def test_completion_writes_job_and_documents_together(self) -> None:
        previous = self.documents.save(
            Document(
                id=DocumentId(f"{self.assistant_id.value}-v1"),
                assistant_id=self.assistant_id,
                source_name="politica.md",
                content_hash=f"hash-{uuid4().hex}",
            )
        )
        document = self._pending_document("-v2")
        job = self._job(document)
        reserved = self.queue.reserve_next(self.now)
        self.assertEqual(reserved.id, job.id)
        processing = self.documents.save(document.start_processing(1))
        self.queue.complete(
            reserved.complete(),
            processing.mark_indexed(
                embedding_model="m", pipeline_version="3", chunk_count=4
            ),
            previous.mark_replaced(),
        )
        self.session.expire_all()
        stored = self.documents.get_by_id(document.id)
        self.assertEqual(stored.status, DocumentStatus.INDEXED)
        self.assertEqual(stored.chunk_count, 4)
        self.assertEqual(stored.size_bytes, 10)
        self.assertEqual(stored.uploaded_by, "teste")
        self.assertEqual(
            self.documents.get_by_id(previous.id).status, DocumentStatus.REPLACED
        )
        listed = self.documents.list_by_assistant(self.assistant_id)
        self.assertEqual([item.id for item in listed], [document.id])

    def test_retry_and_expiry(self) -> None:
        document = self._pending_document()
        self._job(document)
        reserved = self.queue.reserve_next(self.now)
        expired = self.queue.list_expired(self.now + timedelta(seconds=601))
        self.assertIn(reserved.id, [item.id for item in expired])
        processing = self.documents.save(document.start_processing(1))
        later = self.now + timedelta(seconds=30)
        self.queue.retry(
            reserved.retry_at(later, "RuntimeError: x"), processing.retry_later()
        )
        self.assertIsNone(self.queue.reserve_next(self.now))
        again = self.queue.reserve_next(later)
        self.assertEqual((again.id, again.attempts), (reserved.id, 2))
        self.assertEqual(again.last_error, "RuntimeError: x")

    def test_jobs_wait_while_the_assistant_is_reindexed(self) -> None:
        self._job(self._pending_document())
        running = self.reindex_jobs.save(
            ReindexJob(
                id=str(uuid4()),
                assistant_id=self.assistant_id,
                target_collection=f"assistant-{self.assistant_id.value}-v2",
            )
        )
        self.assertIsNone(self.queue.reserve_next(self.now))
        self.reindex_jobs.save(running.succeed())
        self.assertIsNotNone(self.queue.reserve_next(self.now))

    def test_deleting_the_document_removes_its_jobs(self) -> None:
        document = self._pending_document()
        job = self._job(document)
        self.documents.delete(document.id)
        from src.infrastructure.database import IngestionJobModel

        self.assertIsNone(self.session.get(IngestionJobModel, job.id))

    def test_duplicate_lookup_ignores_replaced_versions(self) -> None:
        document = self._pending_document()
        found = self.documents.find_by_hash(self.assistant_id, document.content_hash)
        self.assertEqual(found.id, document.id)
        self.documents.save(
            document.start_processing(1)
            .mark_indexed(embedding_model="m", pipeline_version="3", chunk_count=1)
            .mark_replaced()
        )
        self.assertIsNone(
            self.documents.find_by_hash(self.assistant_id, document.content_hash)
        )

    def test_job_states_round_trip(self) -> None:
        document = self._pending_document()
        job = self._job(document)
        reserved = self.queue.reserve_next(self.now)
        processing = self.documents.save(document.start_processing(1))
        self.queue.fail(reserved.fail("ValueError: x"), processing.mark_failed("Motivo"))
        from src.infrastructure.database import IngestionJobModel

        self.session.expire_all()
        model = self.session.get(IngestionJobModel, job.id)
        self.assertEqual(model.status, IngestionJobStatus.FAILED.value)
        stored = self.documents.get_by_id(document.id)
        self.assertEqual(stored.status, DocumentStatus.FAILED)
        self.assertEqual(stored.failure_reason, "Motivo")


def _chunk(assistant_id: AssistantId, document_id: str, index: int, active: bool):
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
        active=active,
    )


class VectorLifecycleTestCase(unittest.TestCase):
    """CT-38: RN-27, RN-28 e RN-29 no Qdrant."""

    def setUp(self) -> None:
        gateway = _gateway()
        if gateway is None:
            self.skipTest("Qdrant indisponivel")
        self.gateway = gateway
        self.assistant_id = AssistantId(f"teste-ciclo-{uuid4().hex[:12]}")
        self.alias = CollectionName.from_assistant_id(self.assistant_id)
        self.collection = CollectionName.versioned(self.assistant_id, 1)
        gateway.ensure_collection(self.collection, vector_size=4)
        self.addCleanup(gateway.delete_collection, self.collection)
        gateway.point_alias(self.alias, self.collection)

    def _found(self) -> set[str]:
        results = self.gateway.hybrid_search(
            self.alias, VECTOR, SPARSE, limit=20, user_groups=frozenset()
        )
        return {item.document_id.value for item in results}

    def test_inactive_chunks_stay_out_of_every_search(self) -> None:
        self.gateway.upsert_chunks(
            self.alias,
            [
                _chunk(self.assistant_id, "vigente", 0, True),
                _chunk(self.assistant_id, "nova", 0, False),
            ],
        )
        self.assertEqual(self._found(), {"vigente"})
        evaluation = self.gateway.hybrid_search(
            self.alias, VECTOR, SPARSE, limit=20, user_groups=None
        )
        self.assertEqual({item.document_id.value for item in evaluation}, {"vigente"})

        self.gateway.set_document_active(self.alias, DocumentId("nova"), True)
        self.gateway.delete_by_document(self.alias, DocumentId("vigente"))
        self.assertEqual(self._found(), {"nova"})
        self.assertEqual(self.gateway.count_points(self.collection), 1)

    def test_chunks_written_before_the_phase_count_as_active(self) -> None:
        from qdrant_client.http import models

        self.gateway.upsert_chunks(
            self.alias, [_chunk(self.assistant_id, "antigo", 0, True)]
        )
        # Trecho gravado antes da SPEC-005: sem o campo ``active``.
        self.gateway._client.delete_payload(
            collection_name=self.collection.value,
            keys=["active"],
            points=models.Filter(),
            wait=True,
        )
        self.assertEqual(self._found(), {"antigo"})

    def test_delete_by_document_without_collection_is_not_an_error(self) -> None:
        missing = CollectionName.from_assistant_id(AssistantId("nao-existe-ciclo"))
        self.gateway.delete_by_document(missing, DocumentId("doc"))


if __name__ == "__main__":
    unittest.main()
