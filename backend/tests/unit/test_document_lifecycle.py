"""Ingestao assincrona e ciclo de vida do documento (SPEC-20261007-005).

CT-33 (estados e transicoes), CT-34 (novas tentativas e falha definitiva),
CT-35 (worker reiniciado: processamento idempotente e retomavel) e CT-36
(duplicidade, exclusao, substituicao e reprocessamento), com dubles.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from access_doubles import curator, make_user
from test_indexing import MARKDOWN, IndexingTestCase
from src.application.services import (
    TIMEOUT_REASON,
    UNAVAILABLE_SERVICE_REASON,
    IngestionSettings,
)
from src.application.use_cases import (
    DeleteDocumentUseCase,
    DocumentNotFoundError,
    DocumentRefInput,
    GetDocumentUseCase,
    ListDocumentsInput,
    ListDocumentsUseCase,
    ReplaceDocumentInput,
    ReplaceDocumentUseCase,
    ReprocessDocumentInput,
    ReprocessDocumentUseCase,
    RequeueExpiredIngestionJobsUseCase,
)
from src.application.use_cases.manage_conversation import GetConversationUseCase
from src.domain import (
    AccessDeniedError,
    AssistantId,
    AuditAction,
    ChatMessage,
    Citation,
    Conversation,
    ConversationId,
    Document,
    DocumentId,
    DocumentStatus,
    DomainValidationError,
    DuplicateDocumentError,
    IngestionInProgressError,
    IngestionJob,
    IngestionJobStatus,
    InvalidDocumentStateError,
    MessageId,
    MessageRole,
    ReindexInProgressError,
)

NEW_VERSION = b"""# Politica de Ferias

Todo colaborador tem direito a trinta dias de ferias apos doze meses.

## Estagiarios

O recesso agora e de quinze dias.
"""


class _WorkerKilled(BaseException):
    """Simula o processo encerrado no meio do job (nao e ``Exception``)."""


def _document(status: DocumentStatus = DocumentStatus.PENDING, **changes) -> Document:
    values = {
        "id": DocumentId("doc-1"),
        "assistant_id": AssistantId("a1"),
        "source_name": "politica.md",
        "content_hash": "hash",
        "status": status,
        "storage_key": "a1/doc-1.md",
    }
    values.update(changes)
    return Document(**values)


class DocumentStateTestCase(unittest.TestCase):
    """CT-33: transicoes do diagrama de estados da spec."""

    def test_happy_path(self) -> None:
        document = _document().start_processing(1)
        self.assertEqual(document.status, DocumentStatus.PROCESSING)
        self.assertEqual(document.attempts, 1)
        indexed = document.mark_indexed(
            embedding_model="m", pipeline_version="3", chunk_count=4
        )
        self.assertEqual(indexed.status, DocumentStatus.INDEXED)
        self.assertEqual(indexed.chunk_count, 4)
        self.assertTrue(indexed.is_searchable)

    def test_transient_failure_returns_to_pending(self) -> None:
        document = _document().start_processing(1).retry_later()
        self.assertEqual(document.status, DocumentStatus.PENDING)
        self.assertEqual(document.attempts, 1)

    def test_failure_records_reason_and_reprocessing_clears_it(self) -> None:
        failed = _document().start_processing(3).mark_failed("  sem texto ")
        self.assertEqual(failed.status, DocumentStatus.FAILED)
        self.assertEqual(failed.failure_reason, "sem texto")
        again = failed.request_processing()
        self.assertEqual(again.status, DocumentStatus.PENDING)
        self.assertIsNone(again.failure_reason)
        self.assertEqual(again.attempts, 0)

    def test_indexed_document_can_only_be_replaced(self) -> None:
        indexed = _document(DocumentStatus.INDEXED)
        self.assertEqual(indexed.mark_replaced().status, DocumentStatus.REPLACED)
        for move in (
            lambda: indexed.start_processing(1),
            lambda: indexed.mark_failed("x"),
            indexed.request_processing,
        ):
            with self.subTest(move=move), self.assertRaises(InvalidDocumentStateError):
                move()

    def test_forbidden_transitions(self) -> None:
        pending = _document()
        with self.assertRaises(InvalidDocumentStateError):
            pending.mark_indexed(embedding_model="m", pipeline_version="3", chunk_count=1)
        with self.assertRaises(InvalidDocumentStateError):
            pending.request_processing()
        with self.assertRaises(InvalidDocumentStateError):
            _document(DocumentStatus.REPLACED).start_processing(1)

    def test_reprocessing_requires_the_stored_original(self) -> None:
        failed = _document(DocumentStatus.FAILED, storage_key=None)
        with self.assertRaises(InvalidDocumentStateError):
            failed.request_processing()

    def test_invariants(self) -> None:
        for changes in (
            {"version": 0},
            {"attempts": -1},
            {"size_bytes": -1},
            {"replaces_document_id": DocumentId("doc-1")},
        ):
            with self.subTest(changes=changes), self.assertRaises(DomainValidationError):
                _document(**changes)
        with self.assertRaises(DomainValidationError):
            _document().start_processing(1).mark_failed("  ")

    def test_documents_before_the_phase_count_as_indexed(self) -> None:
        legacy = Document(
            id=DocumentId("antigo"),
            assistant_id=AssistantId("a1"),
            source_name="antigo.txt",
            content_hash="hash",
        )
        self.assertEqual(legacy.status, DocumentStatus.INDEXED)
        self.assertEqual(legacy.version, 1)


class IngestionJobTestCase(unittest.TestCase):
    def test_reserve_counts_the_attempt(self) -> None:
        now = datetime(2026, 10, 8, tzinfo=UTC)
        job = IngestionJob(id="j1", document_id=DocumentId("doc-1")).reserve(now)
        self.assertEqual(job.status, IngestionJobStatus.PROCESSING)
        self.assertEqual(job.attempts, 1)
        self.assertEqual(job.reserved_at, now)
        with self.assertRaises(DomainValidationError):
            job.reserve(now)

    def test_retry_releases_the_reservation(self) -> None:
        now = datetime(2026, 10, 8, tzinfo=UTC)
        job = (
            IngestionJob(id="j1", document_id=DocumentId("doc-1"))
            .reserve(now)
            .retry_at(now + timedelta(seconds=30), "RuntimeError: x")
        )
        self.assertEqual(job.status, IngestionJobStatus.PENDING)
        self.assertIsNone(job.reserved_at)
        self.assertEqual(job.attempts, 1)
        self.assertEqual(job.last_error, "RuntimeError: x")

    def test_settings_follow_decision_d7(self) -> None:
        settings = IngestionSettings()
        self.assertEqual(settings.max_attempts, 3)
        self.assertEqual(settings.delay_after(1), timedelta(seconds=30))
        self.assertEqual(settings.delay_after(2), timedelta(seconds=120))
        self.assertEqual(settings.delay_after(5), timedelta(seconds=120))
        self.assertEqual(settings.job_timeout, timedelta(seconds=600))
        with self.assertRaises(ValueError):
            IngestionSettings(max_attempts=0)


class LifecycleTestCase(IndexingTestCase):
    @property
    def store(self):
        return self.scenario.vector_store

    def chunks(self, assistant: str = "a1") -> dict:
        alias = self.store.aliases.get(f"assistant-{assistant}")
        return self.store.collections.get(alias, {}) if alias else {}

    def documents_in_index(self) -> set[str]:
        return {chunk.document_id.value for chunk in self.chunks().values()}

    def active_documents(self) -> set[str]:
        return {
            chunk.document_id.value
            for chunk in self.chunks().values()
            if chunk.active
        }

    def doc(self, document_id: str = "doc-1") -> Document:
        return self.scenario.documents.items[document_id]

    def requeue_expired(self):
        return RequeueExpiredIngestionJobsUseCase(
            job_queue=self.scenario.queue,
            document_repository=self.scenario.documents,
            vector_store_gateway=self.store,
            access_control=self.scenario.access.control,
            clock=self.scenario.clock,
        ).execute()

    def delete(self, document_id: str = "doc-1", user=None) -> None:
        DeleteDocumentUseCase(
            document_repository=self.scenario.documents,
            vector_store_gateway=self.store,
            file_storage=self.scenario.storage,
            reindex_job_repository=self.scenario.jobs,
            access_control=self.scenario.access.control,
        ).execute(
            DocumentRefInput(user=user or self.scenario.user, document_id=document_id)
        )
        self.scenario.queue.drop_jobs_of_deleted_documents()

    def replace_with(
        self,
        content: bytes = NEW_VERSION,
        document_id: str = "doc-1",
        new_document_id: str = "doc-1-v2",
        source_name: str = "politica-2026.md",
    ):
        return ReplaceDocumentUseCase(
            document_repository=self.scenario.documents,
            vector_store_gateway=self.store,
            document_indexer=self.scenario.indexer,
            file_storage=self.scenario.storage,
            job_queue=self.scenario.queue,
            max_file_bytes=4096,
            access_control=self.scenario.access.control,
        ).execute(
            ReplaceDocumentInput(
                user=self.scenario.user,
                document_id=document_id,
                source_name=source_name,
                raw_content=content,
                new_document_id=new_document_id,
            )
        )

    def reprocess(self, document_id: str = "doc-1"):
        return ReprocessDocumentUseCase(
            document_repository=self.scenario.documents,
            job_queue=self.scenario.queue,
            access_control=self.scenario.access.control,
        ).execute(
            ReprocessDocumentInput(user=self.scenario.user, document_id=document_id)
        )

    def get(self, document_id: str = "doc-1", user=None):
        return GetDocumentUseCase(
            document_repository=self.scenario.documents,
            access_control=self.scenario.access.control,
        ).execute(
            DocumentRefInput(user=user or self.scenario.user, document_id=document_id)
        )


class AsynchronousUploadTestCase(LifecycleTestCase):
    """RF-48, RF-49, RN-27."""

    def test_upload_answers_pending_without_touching_the_index(self) -> None:
        result = self.scenario.upload()
        self.assertEqual(result.status, "pendente")
        self.assertEqual(result.chunk_count, 0)
        self.assertEqual(result.size_bytes, len(MARKDOWN))
        self.assertEqual(self.store.collections, {})
        self.assertEqual(len(self.scenario.queue.pending()), 1)
        self.assertEqual(self.get().status, "pendente")

    def test_worker_takes_the_document_to_indexed(self) -> None:
        self.scenario.upload()
        outcome = self.scenario.process()
        self.assertEqual(outcome.status, "indexado")
        self.assertEqual(self.get().status, "indexado")
        self.assertEqual(self.get().chunk_count, len(self.chunks()))
        self.assertEqual(self.active_documents(), {"doc-1"})
        self.assertIsNone(self.scenario.process())
        event = self.scenario.access.audit.last(AuditAction.DOCUMENT_INDEXED)
        self.assertEqual(event.user_id, "system:worker")

    def test_groups_are_stored_before_the_job_runs(self) -> None:
        """C6: o worker ja grava os trechos restritos."""
        from src.application.use_cases import IngestDocumentInput, IngestDocumentUseCase

        IngestDocumentUseCase(
            document_repository=self.scenario.documents,
            vector_store_gateway=self.store,
            document_indexer=self.scenario.indexer,
            file_storage=self.scenario.storage,
            job_queue=self.scenario.queue,
            max_file_bytes=4096,
            access_control=self.scenario.access.control,
        ).execute(
            IngestDocumentInput(
                user=self.scenario.user,
                assistant_id="a1",
                document_id="doc-1",
                source_name="politica.md",
                raw_content=MARKDOWN,
                groups=("diretoria",),
            )
        )
        self.scenario.process()
        self.assertTrue(self.chunks())
        self.assertTrue(
            all(chunk.allowed_groups == ("diretoria",) for chunk in self.chunks().values())
        )

    def test_failed_enqueue_leaves_no_document_or_file(self) -> None:
        self.scenario.queue.fail_next_enqueue = True
        with self.assertRaises(RuntimeError):
            self.scenario.upload()
        self.assertEqual(self.scenario.documents.items, {})
        with self.assertRaises(FileNotFoundError):
            self.scenario.storage.load("a1/doc-1.md")

    def test_listing_shows_state_version_and_reason(self) -> None:
        self.scenario.ingest()
        self.scenario.upload(document_id="doc-2", source_name="vazio.txt", raw_content=b" ")
        self.scenario.process()
        listed = ListDocumentsUseCase(
            document_repository=self.scenario.documents,
            access_control=self.scenario.access.control,
        ).execute(ListDocumentsInput(user=self.scenario.user, assistant_id="a1"))
        by_id = {item.id: item for item in listed}
        self.assertEqual(by_id["doc-1"].status, "indexado")
        self.assertEqual(by_id["doc-1"].version, 1)
        self.assertEqual(by_id["doc-2"].status, "falhou")
        self.assertTrue(by_id["doc-2"].failure_reason)

    def test_user_without_management_cannot_read_the_state(self) -> None:
        self.scenario.upload()
        with self.assertRaises(AccessDeniedError):
            self.get(user=make_user("ana", groups=("rh",)))


class RetryTestCase(LifecycleTestCase):
    """CT-34: RF-55, RN-30, D7."""

    def test_transient_failures_are_retried_after_30_and_120_seconds(self) -> None:
        self.store.fail_upsert_into = "assistant-a1-v1"
        self.scenario.upload()

        first = self.scenario.process()
        self.assertEqual((first.status, first.attempts), ("pendente", 1))
        self.assertEqual(self.doc().status, DocumentStatus.PENDING)
        self.assertIsNone(self.scenario.process())
        self.scenario.clock.advance(30)

        second = self.scenario.process()
        self.assertEqual((second.status, second.attempts), ("pendente", 2))
        self.scenario.clock.advance(119)
        self.assertIsNone(self.scenario.process())
        self.scenario.clock.advance(1)

        third = self.scenario.process()
        self.assertEqual((third.status, third.attempts), ("falhou", 3))
        self.assertEqual(self.doc().status, DocumentStatus.FAILED)
        self.assertEqual(self.doc().failure_reason, UNAVAILABLE_SERVICE_REASON)
        self.assertEqual(self.scenario.queue.pending(), [])
        event = self.scenario.access.audit.last(AuditAction.DOCUMENT_FAILED)
        self.assertEqual(event.details["attempts"], 3)
        self.assertNotIn("RuntimeError", event.details["reason"])

    def test_recovery_on_a_later_attempt_indexes_the_document(self) -> None:
        self.store.fail_upsert_into = "assistant-a1-v1"
        self.scenario.upload()
        self.scenario.process()
        self.store.fail_upsert_into = None
        self.scenario.clock.advance(30)
        outcome = self.scenario.process()
        self.assertEqual((outcome.status, outcome.attempts), ("indexado", 2))
        self.assertIsNone(self.doc().failure_reason)

    def test_reprocessing_a_failed_document_without_new_upload(self) -> None:
        """Cenario "Reprocessar sem novo upload"."""
        self.store.fail_upsert_into = "assistant-a1-v1"
        self.scenario.upload()
        for _ in range(3):
            self.scenario.process()
            self.scenario.clock.advance(120)
        self.assertEqual(self.doc().status, DocumentStatus.FAILED)

        self.store.fail_upsert_into = None
        result = self.reprocess()
        self.assertEqual(result.status, "pendente")
        self.assertIsNone(result.failure_reason)
        outcome = self.scenario.process()
        self.assertEqual((outcome.status, outcome.attempts), ("indexado", 1))
        self.assertIn(
            AuditAction.DOCUMENT_REPROCESSED, self.scenario.access.audit.actions()
        )

    def test_only_failed_documents_are_reprocessed(self) -> None:
        self.scenario.ingest()
        with self.assertRaises(InvalidDocumentStateError):
            self.reprocess()
        with self.assertRaises(DocumentNotFoundError):
            self.reprocess("nao-existe")


class WorkerRestartTestCase(LifecycleTestCase):
    """CT-35: RNF-27 e cenario "Worker reiniciado"."""

    def _kill_worker_on_activation(self) -> None:
        original = self.store.set_document_active

        def killed(*args, **kwargs):
            self.store.set_document_active = original
            raise _WorkerKilled()

        self.store.set_document_active = killed

    def test_interrupted_job_resumes_with_the_same_chunk_count(self) -> None:
        reference = self._clean_run_chunk_count()
        self.scenario.upload()
        self._kill_worker_on_activation()
        with self.assertRaises(_WorkerKilled):
            self.scenario.process()
        # Trechos gravados, mas fora das buscas (RN-27).
        self.assertEqual(self.doc().status, DocumentStatus.PROCESSING)
        self.assertTrue(self.chunks())
        self.assertEqual(self.active_documents(), set())

        self.assertEqual(self.requeue_expired(), [])
        self.scenario.clock.advance(601)
        outcomes = self.requeue_expired()
        self.assertEqual([item.status for item in outcomes], ["pendente"])
        self.scenario.clock.advance(30)

        outcome = self.scenario.process()
        self.assertEqual((outcome.status, outcome.attempts), ("indexado", 2))
        self.assertEqual(len(self.chunks()), reference)
        self.assertEqual(outcome.chunk_count, reference)
        self.assertEqual(self.active_documents(), {"doc-1"})

    def test_job_expired_on_the_last_attempt_fails(self) -> None:
        self.scenario.upload()
        for _ in range(3):
            self._kill_worker_on_activation()
            with self.assertRaises(_WorkerKilled):
                self.scenario.process()
            self.scenario.clock.advance(601)
            self.requeue_expired()
            self.scenario.clock.advance(120)
        self.assertEqual(self.doc().status, DocumentStatus.FAILED)
        self.assertEqual(self.doc().failure_reason, TIMEOUT_REASON)
        self.assertEqual(self.chunks(), {})

    def _clean_run_chunk_count(self) -> int:
        self.scenario.ingest(assistant_id="ref", document_id="ref-1")
        return self.scenario.documents.items["ref-1"].chunk_count


class DuplicateTestCase(LifecycleTestCase):
    """RN-26, D9 e cenario "Arquivo duplicado"."""

    def test_same_file_points_to_the_existing_document(self) -> None:
        self.scenario.ingest()
        chunks_before = dict(self.chunks())
        with self.assertRaises(DuplicateDocumentError) as raised:
            self.scenario.upload(document_id="doc-9", raw_content=MARKDOWN)
        self.assertEqual(raised.exception.existing_document_id, "doc-1")
        self.assertNotIn("doc-9", self.scenario.documents.items)
        self.assertEqual(self.chunks(), chunks_before)
        self.assertEqual(self.scenario.queue.pending(), [])

    def test_duplicate_of_a_failed_or_pending_document_is_reported(self) -> None:
        self.scenario.upload()
        with self.assertRaises(DuplicateDocumentError):
            self.scenario.upload(document_id="doc-9", raw_content=MARKDOWN)

    def test_other_assistants_may_hold_the_same_file(self) -> None:
        self.scenario.ingest(assistant_id="a1", document_id="doc-1")
        self.scenario.ingest(assistant_id="a2", document_id="doc-2", raw_content=MARKDOWN)
        self.assertEqual(
            self.scenario.documents.items["doc-2"].status, DocumentStatus.INDEXED
        )


class DeleteTestCase(LifecycleTestCase):
    """RF-50, RN-29 e cenario "Excluir documento"."""

    def test_delete_removes_chunks_file_and_record(self) -> None:
        self.scenario.ingest()
        storage_key = self.doc().storage_key
        self.delete()
        self.assertEqual(self.chunks(), {})
        self.assertNotIn("doc-1", self.scenario.documents.items)
        with self.assertRaises(FileNotFoundError):
            self.scenario.storage.load(storage_key or "")
        event = self.scenario.access.audit.last(AuditAction.DOCUMENT_DELETED)
        self.assertEqual(event.resource_id, "doc-1")
        self.assertEqual(event.details["source_name"], "politica.md")

    def test_delete_only_touches_the_chosen_document(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        self.scenario.ingest(document_id="doc-2")
        self.delete("doc-1")
        self.assertEqual(self.documents_in_index(), {"doc-2"})

    def test_pending_document_can_be_deleted_and_its_job_is_dropped(self) -> None:
        self.scenario.upload()
        self.delete()
        self.assertEqual(self.scenario.queue.jobs, {})
        self.assertIsNone(self.scenario.process())

    def test_delete_during_processing_wins(self) -> None:
        """C4: o worker remove o que gravou e nao ativa nada."""
        self.scenario.upload()
        original = self.store.upsert_chunks

        def upsert_then_delete(collection_name, chunks):
            original(collection_name, chunks)
            self.scenario.documents.delete(DocumentId("doc-1"))

        self.store.upsert_chunks = upsert_then_delete
        self.assertIsNone(self.scenario.process())
        self.assertEqual(self.chunks(), {})

    def test_curator_of_another_area_cannot_delete(self) -> None:
        self.scenario.ingest()
        self.scenario.access.link_assistant("a1", "rh")
        with self.assertRaises(AccessDeniedError):
            self.delete(user=curator("eva", "financeiro"))
        self.assertIn("doc-1", self.scenario.documents.items)

    def test_delete_is_refused_during_a_reindex(self) -> None:
        self.scenario.ingest()
        self.scenario.start_reindex()
        with self.assertRaises(ReindexInProgressError):
            self.delete()
        self.assertIn("doc-1", self.scenario.documents.items)

    def test_unknown_document(self) -> None:
        with self.assertRaises(DocumentNotFoundError):
            self.delete("nao-existe")


class ReplaceTestCase(LifecycleTestCase):
    """RF-51, RN-28, D5 e cenario "Substituir documento"."""

    def test_previous_version_answers_until_the_new_one_is_indexed(self) -> None:
        self.scenario.ingest()
        self.scenario.access.restrict_document("doc-1", "rh")
        old_key = self.doc().storage_key
        result = self.replace_with()
        self.assertEqual((result.status, result.version), ("pendente", 2))
        self.assertEqual(result.replaces_document_id, "doc-1")
        self.assertEqual(result.groups, ("rh",))
        self.assertEqual(self.active_documents(), {"doc-1"})

        self.scenario.process()
        self.assertEqual(self.documents_in_index(), {"doc-1-v2"})
        self.assertEqual(self.active_documents(), {"doc-1-v2"})
        self.assertEqual(self.doc().status, DocumentStatus.REPLACED)
        self.assertEqual(self.doc("doc-1-v2").status, DocumentStatus.INDEXED)
        self.assertTrue(
            all(chunk.allowed_groups == ("rh",) for chunk in self.chunks().values())
        )
        with self.assertRaises(FileNotFoundError):
            self.scenario.storage.load(old_key or "")
        listed = self.scenario.documents.list_by_assistant(AssistantId("a1"))
        self.assertEqual([item.id.value for item in listed], ["doc-1-v2"])
        with self.assertRaises(DocumentNotFoundError):
            self.get("doc-1")

    def test_failed_new_version_keeps_the_previous_one(self) -> None:
        self.scenario.ingest()
        self.replace_with(content=b"   ", source_name="vazio.txt")
        self.scenario.process()
        self.assertEqual(self.doc().status, DocumentStatus.INDEXED)
        self.assertEqual(self.doc("doc-1-v2").status, DocumentStatus.FAILED)
        self.assertEqual(self.active_documents(), {"doc-1"})

    def test_identical_new_version_is_a_duplicate(self) -> None:
        self.scenario.ingest()
        with self.assertRaises(DuplicateDocumentError):
            self.replace_with(content=MARKDOWN)

    def test_only_indexed_documents_receive_new_versions(self) -> None:
        self.scenario.upload()
        with self.assertRaises(InvalidDocumentStateError):
            self.replace_with()

    def test_one_pending_version_at_a_time(self) -> None:
        self.scenario.ingest()
        self.replace_with()
        with self.assertRaises(InvalidDocumentStateError):
            self.replace_with(content=NEW_VERSION + b"\nOutra.", new_document_id="v3")

    def test_deleting_the_current_version_drops_the_pending_one(self) -> None:
        self.scenario.ingest()
        self.replace_with()
        self.delete("doc-1")
        self.assertEqual(self.scenario.documents.items, {})
        self.assertIsNone(self.scenario.process())


class ReindexInteractionTestCase(LifecycleTestCase):
    def test_reindex_waits_for_documents_being_processed(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        self.scenario.upload(document_id="doc-2")
        doc = self.doc("doc-2")
        self.scenario.documents.save(doc.start_processing(1))
        with self.assertRaises(IngestionInProgressError):
            self.scenario.start_reindex()

    def test_reindex_skips_documents_that_are_not_indexed(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        self.scenario.upload(document_id="doc-2", source_name="vazio.txt", raw_content=b" ")
        self.scenario.process()
        job = self.scenario.start_reindex()
        self.assertEqual(job.total_documents, 1)
        self.assertEqual(self.scenario.run_reindex(job.id).status, "succeeded")


class RemovedSourcesTestCase(LifecycleTestCase):
    """RN-29, D10: citacoes antigas ficam marcadas."""

    def test_citations_of_deleted_or_replaced_documents_are_marked(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        self.scenario.ingest(document_id="doc-2")
        self.scenario.ingest(document_id="doc-3")
        self.delete("doc-1")
        self.replace_with(document_id="doc-2", new_document_id="doc-2-v2")
        self.scenario.process()

        conversation = Conversation(
            id=ConversationId("c1"),
            assistant_id=AssistantId("a1"),
            messages=(
                ChatMessage(
                    id=MessageId("m1"),
                    conversation_id=ConversationId("c1"),
                    role=MessageRole.ASSISTANT,
                    content="Resposta [1] [2] [3]",
                    citations=tuple(
                        Citation(
                            number=number,
                            document_id=DocumentId(document_id),
                            chunk_id=f"{document_id}:0",
                            source_name="politica.md",
                            excerpt="trecho",
                        )
                        for number, document_id in enumerate(
                            ("doc-1", "doc-2", "doc-3"), start=1
                        )
                    ),
                ),
            ),
        )
        use_case = GetConversationUseCase(
            None,  # type: ignore[arg-type]
            self.scenario.access.control,
            self.scenario.documents,
        )
        self.assertEqual(
            use_case.removed_sources(conversation), frozenset({"doc-1", "doc-2"})
        )


if __name__ == "__main__":
    unittest.main()
