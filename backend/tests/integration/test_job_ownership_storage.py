"""SPEC-007 fix-3: UPDATEs condicionais ao dono do job no PostgreSQL.

Exige o PostgreSQL do Compose (execute dentro do container do backend).
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    Document,
    DocumentId,
    DocumentStatus,
    IngestionJob,
    JobOwnershipLostError,
    ReindexJob,
    ReindexStatus,
)


def _session():
    try:
        from sqlalchemy import text

        from src.infrastructure.database import SessionLocal, run_migrations

        run_migrations()
        session = SessionLocal()
        session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - banco indisponivel pula o teste
        return None
    return session


class JobOwnershipStorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        session = _session()
        if session is None:
            self.skipTest("PostgreSQL indisponivel")
        from src.infrastructure.database import (
            PostgresAssistantRepository,
            PostgresDocumentRepository,
            PostgresIngestionJobQueue,
            PostgresReindexJobRepository,
        )

        self.session = session
        self.addCleanup(session.close)
        self.queue = PostgresIngestionJobQueue(session=session)
        self.reindex = PostgresReindexJobRepository(session=session)
        self.assistant_id = AssistantId(f"teste-dono-{uuid4().hex[:12]}")
        assistants = PostgresAssistantRepository(session=session)
        assistants.save(Assistant(id=self.assistant_id, name=AssistantName("Dono")))
        self.addCleanup(assistants.delete, self.assistant_id)
        self.documents = PostgresDocumentRepository(session=session)
        self.now = datetime(2000, 1, 1, tzinfo=UTC)

    def _document(self) -> Document:
        return self.documents.save(
            Document(
                id=DocumentId(f"{self.assistant_id.value}-doc"),
                assistant_id=self.assistant_id,
                source_name="politica.md",
                content_hash=f"hash-{uuid4().hex}",
                status=DocumentStatus.PENDING,
                storage_key="a/b.md",
                size_bytes=10,
                uploaded_by="teste",
            )
        )

    def test_ingestion_job_is_written_only_by_the_current_owner(self) -> None:
        document = self._document()
        job = self.queue.enqueue(
            IngestionJob(
                id=str(uuid4()),
                document_id=document.id,
                available_at=self.now,
                created_at=self.now,
            )
        )
        first = self.queue.reserve_next(self.now)
        self.assertEqual(first.id, job.id)
        self.assertTrue(self.queue.renew(first, self.now + timedelta(seconds=5)))
        # A reserva expira e o job volta; outro worker o assume (tentativa 2).
        self.queue.retry(first.retry_at(self.now, "timeout"), document)
        second = self.queue.reserve_next(self.now + timedelta(seconds=1))
        self.assertEqual(second.attempts, 2)

        self.assertFalse(self.queue.renew(first, self.now))
        with self.assertRaises(JobOwnershipLostError):
            self.queue.complete(first.complete(), document)
        self.queue.complete(second.complete(), document)

    def test_reindex_lease_and_result_follow_the_attempt(self) -> None:
        job = self.reindex.save(
            ReindexJob(
                id=str(uuid4()),
                assistant_id=self.assistant_id,
                target_collection=f"{self.assistant_id.value}-v2",
            )
        )
        lease = timedelta(seconds=60)
        claimed = self.reindex.claim_next(self.now, lease)
        self.assertEqual(claimed.id, job.id)
        until = self.now + lease
        self.assertTrue(
            self.reindex.renew_lease(
                job.id, 1, lease_expires_at=until, processed_documents=3
            )
        )
        self.assertFalse(
            self.reindex.renew_lease(
                job.id, 2, lease_expires_at=until, processed_documents=9
            )
        )
        self.assertEqual(self.reindex.get_by_id(job.id).processed_documents, 3)

        finished = self.reindex.get_by_id(job.id).succeed()
        self.assertFalse(self.reindex.save_if_owner(finished, 2))
        self.assertEqual(self.reindex.get_by_id(job.id).status, ReindexStatus.RUNNING)
        self.assertTrue(self.reindex.save_if_owner(finished, 1))
        self.assertEqual(self.reindex.get_by_id(job.id).status, ReindexStatus.SUCCEEDED)


if __name__ == "__main__":
    unittest.main()
