"""Ingestao, reindexacao e situacao do indice (SPEC-20261007-002)."""

import logging
from datetime import datetime, timedelta
from dataclasses import replace
import tempfile
import unittest

from access_doubles import AccessFixture, admin
from ingestion_doubles import (
    InMemoryIngestionJobQueue,
    ManualClock,
    current_documents,
    find_current_by_hash,
)
from src.application.services import (
    PIPELINE_VERSION,
    UNREADABLE_DOCUMENT_REASON,
    DocumentIndexer,
)
from src.application.use_cases import (
    DocumentTooLargeError,
    GetIndexStatusInput,
    GetIndexStatusUseCase,
    IngestDocumentInput,
    IngestDocumentUseCase,
    ProcessNextIngestionJobUseCase,
    ProcessNextReindexJobUseCase,
    ReindexJobNotFoundError,
    ReindexSettings,
    RunReindexInput,
    RunReindexUseCase,
    StartReindexInput,
    StartReindexUseCase,
)
from src.domain import (
    AssistantId,
    CollectionName,
    Document,
    DocumentId,
    DocumentStatus,
    IndexOutdatedError,
    ReindexInProgressError,
    ReindexJob,
    ReindexStatus,
    SearchResult,
    SparseVector,
    VectorChunk,
)
from src.infrastructure.chunking import StructuralDocumentChunker
from src.infrastructure.documents import SupportedDocumentExtractor
from src.infrastructure.embeddings import (
    Bm25SparseEmbeddingGateway,
    LocalHashEmbeddingGateway,
)
from src.infrastructure.storage import LocalDocumentFileStorage

MODEL = "modelo-teste"
MAX_BYTES = 1024

MARKDOWN = b"""# Politica de Ferias

Todo colaborador tem direito a ferias apos doze meses.

## Estagiarios

O recesso e de trinta dias. Ele e proporcional em contratos menores.
"""


class WordTokenCounter:
    max_tokens = 128

    def count(self, text: str) -> int:
        return len(text.split()) + 2


class FakeEmbeddingGateway:
    def __init__(self, model_name: str = MODEL) -> None:
        self.model_name = model_name
        self.dimension = 2

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 1.0]


class InMemoryVectorStore:
    """Collections fisicas e aliases, como no Qdrant."""

    def __init__(self) -> None:
        self.collections: dict[str, dict[str, VectorChunk]] = {}
        self.aliases: dict[str, str] = {}
        self.fail_upsert_into: str | None = None
        self.lose_points = False

    def _physical(self, collection_name: CollectionName) -> str:
        return self.aliases.get(collection_name.value, collection_name.value)

    def ensure_collection(
        self,
        collection_name: CollectionName,
        vector_size: int,
    ) -> None:
        self.collections.setdefault(collection_name.value, {})

    def upsert_chunks(
        self,
        collection_name: CollectionName,
        chunks: list[VectorChunk],
    ) -> None:
        physical = self._physical(collection_name)
        if physical == self.fail_upsert_into:
            raise RuntimeError("vector store unavailable")
        if self.lose_points:
            chunks = chunks[:-1]
        self.collections[physical].update({chunk.id: chunk for chunk in chunks})

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
        return []

    def set_document_groups(
        self,
        collection_name: CollectionName,
        document_id: DocumentId,
        groups: frozenset[str],
    ) -> None:
        raise AssertionError("not used by these tests")

    def delete_by_document(
        self,
        collection_name: CollectionName,
        document_id: DocumentId,
    ) -> None:
        points = self.collections.get(self._physical(collection_name))
        if points is None:
            return
        for key in [k for k, chunk in points.items() if chunk.document_id == document_id]:
            del points[key]

    def set_document_active(
        self,
        collection_name: CollectionName,
        document_id: DocumentId,
        active: bool,
    ) -> None:
        points = self.collections.get(self._physical(collection_name), {})
        for key, chunk in list(points.items()):
            if chunk.document_id == document_id:
                points[key] = replace(chunk, active=active)

    def delete_collection(self, collection_name: CollectionName) -> None:
        self.collections.pop(collection_name.value, None)
        self.aliases = {
            alias: target
            for alias, target in self.aliases.items()
            if target != collection_name.value
        }

    def collection_exists(self, collection_name: CollectionName) -> bool:
        return collection_name.value in self.collections

    def count_points(self, collection_name: CollectionName) -> int:
        return len(self.collections[self._physical(collection_name)])

    def resolve_alias(self, alias: CollectionName) -> CollectionName | None:
        target = self.aliases.get(alias.value)
        return CollectionName(target) if target else None

    def point_alias(
        self,
        alias: CollectionName,
        collection_name: CollectionName,
    ) -> None:
        if alias.value in self.collections:
            raise RuntimeError("alias name is taken by a collection")
        self.aliases[alias.value] = collection_name.value


class InMemoryDocumentRepository:
    def __init__(self) -> None:
        self.items: dict[str, Document] = {}

    def save(self, document: Document) -> Document:
        self.items[document.id.value] = document
        return document

    def get_by_id(self, document_id: DocumentId) -> Document | None:
        return self.items.get(document_id.value)

    def list_by_assistant(self, assistant_id: AssistantId) -> list[Document]:
        return current_documents(self.items, assistant_id)

    def find_by_hash(
        self,
        assistant_id: AssistantId,
        content_hash: str,
    ) -> Document | None:
        return find_current_by_hash(self.items, assistant_id, content_hash)

    def delete(self, document_id: DocumentId) -> bool:
        return self.items.pop(document_id.value, None) is not None


class InMemoryReindexJobRepository:
    def __init__(self) -> None:
        self.items: dict[str, ReindexJob] = {}

    def save(self, job: ReindexJob) -> ReindexJob:
        running = self.get_running(job.assistant_id)
        if job.is_running and running is not None and running.id != job.id:
            raise ReindexInProgressError("already running")
        self.items[job.id] = job
        return job

    def get_by_id(self, job_id: str) -> ReindexJob | None:
        return self.items.get(job_id)

    def get_latest(self, assistant_id: AssistantId) -> ReindexJob | None:
        jobs = [
            job for job in self.items.values() if job.assistant_id == assistant_id
        ]
        return max(jobs, key=lambda job: job.started_at) if jobs else None

    def get_running(self, assistant_id: AssistantId) -> ReindexJob | None:
        for job in self.items.values():
            if job.assistant_id == assistant_id and job.is_running:
                return job
        return None

    def list_running(self) -> list[ReindexJob]:
        return [job for job in self.items.values() if job.is_running]

    def claim_next(self, now: datetime, lease: timedelta) -> ReindexJob | None:
        claimable = sorted(
            (job for job in self.items.values() if job.is_claimable(now)),
            key=lambda job: job.started_at,
        )
        if not claimable:
            return None
        claimed = claimable[0].claim(now, lease)
        self.items[claimed.id] = claimed
        return claimed


class Scenario:
    """Monta os casos de uso sobre os mesmos dubles."""

    def __init__(self, base_dir: str, model_name: str = MODEL) -> None:
        self.documents = InMemoryDocumentRepository()
        self.vector_store = InMemoryVectorStore()
        self.jobs = InMemoryReindexJobRepository()
        self.storage = LocalDocumentFileStorage(base_dir=base_dir)
        self.queue = InMemoryIngestionJobQueue(self.documents, self.jobs)
        self.clock = ManualClock()
        self.max_file_bytes = MAX_BYTES
        self.access = AccessFixture()
        self.user = admin()
        self.use_model(model_name)

    def use_model(self, model_name: str) -> None:
        self.embedding = FakeEmbeddingGateway(model_name)
        self.indexer = DocumentIndexer(
            extractor=SupportedDocumentExtractor(),
            chunker=StructuralDocumentChunker(
                token_counter=WordTokenCounter(),
                max_tokens=24,
                overlap_sentences=1,
                max_prefix_tokens=8,
            ),
            embedding_gateway=self.embedding,
            sparse_embedding_gateway=Bm25SparseEmbeddingGateway(),
        )

    def upload(
        self,
        assistant_id: str = "a1",
        document_id: str = "doc-1",
        source_name: str = "politica.md",
        raw_content: bytes | None = None,
    ):
        if raw_content is None:
            # RN-26: cada documento precisa de conteudo proprio.
            suffix = b"" if document_id == "doc-1" else f"\nRevisao {document_id}.\n".encode()
            raw_content = MARKDOWN + suffix
        return IngestDocumentUseCase(
            document_repository=self.documents,
            vector_store_gateway=self.vector_store,
            document_indexer=self.indexer,
            file_storage=self.storage,
            job_queue=self.queue,
            max_file_bytes=self.max_file_bytes,
            access_control=self.access.control,
        ).execute(
            IngestDocumentInput(
                user=self.user,
                assistant_id=assistant_id,
                document_id=document_id,
                source_name=source_name,
                raw_content=raw_content,
                metadata={"origem": "teste"},
            )
        )

    def process(self):
        return ProcessNextIngestionJobUseCase(
            job_queue=self.queue,
            document_repository=self.documents,
            vector_store_gateway=self.vector_store,
            document_indexer=self.indexer,
            file_storage=self.storage,
            reindex_job_repository=self.jobs,
            access_control=self.access.control,
            clock=self.clock,
        ).execute()

    def ingest(self, **kwargs):
        """Envio seguido do processamento pelo worker."""
        self.upload(**kwargs)
        return self.process()

    def start_reindex(self, assistant_id: str = "a1"):
        return StartReindexUseCase(
            document_repository=self.documents,
            vector_store_gateway=self.vector_store,
            reindex_job_repository=self.jobs,
            access_control=self.access.control,
        ).execute(StartReindexInput(user=self.user, assistant_id=assistant_id))

    def run_reindex(self, job_id: str):
        return RunReindexUseCase(
            document_repository=self.documents,
            vector_store_gateway=self.vector_store,
            document_indexer=self.indexer,
            file_storage=self.storage,
            reindex_job_repository=self.jobs,
            permission_repository=self.access.permissions,
        ).execute(RunReindexInput(job_id=job_id))

    def status(self, assistant_id: str = "a1"):
        return GetIndexStatusUseCase(
            document_repository=self.documents,
            vector_store_gateway=self.vector_store,
            embedding_gateway=self.embedding,
            reindex_job_repository=self.jobs,
            access_control=self.access.control,
        ).execute(GetIndexStatusInput(user=self.user, assistant_id=assistant_id))

    def add_legacy_base(self, assistant_id: str = "a1") -> None:
        """Estado deixado pelo MVP: collection sem versao e documento sem original."""
        self.vector_store.collections[f"assistant-{assistant_id}"] = {}
        self.documents.save(
            Document(
                id=DocumentId("legado"),
                assistant_id=AssistantId(assistant_id),
                source_name="antigo.txt",
                content_hash="hash",
            )
        )


class IndexingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.scenario = Scenario(directory.name)
        # As falhas simuladas sao registradas em log pelo caso de uso.
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)


class IngestDocumentTestCase(IndexingTestCase):
    def test_first_ingestion_creates_versioned_collection_and_alias(self) -> None:
        result = self.scenario.ingest()
        store = self.scenario.vector_store
        self.assertEqual(result.status, "indexado")
        self.assertEqual(store.aliases, {"assistant-a1": "assistant-a1-v1"})
        self.assertEqual(len(store.collections["assistant-a1-v1"]), result.chunk_count)
        self.assertGreaterEqual(result.chunk_count, 2)

    def test_second_ingestion_reuses_current_collection(self) -> None:
        first = self.scenario.ingest(document_id="doc-1")
        second = self.scenario.ingest(document_id="doc-2")
        store = self.scenario.vector_store
        self.assertEqual(list(store.collections), ["assistant-a1-v1"])
        self.assertEqual(
            len(store.collections["assistant-a1-v1"]),
            first.chunk_count + second.chunk_count,
        )

    def test_assistants_do_not_share_collections(self) -> None:
        self.scenario.ingest(assistant_id="a1", document_id="doc-1")
        self.scenario.ingest(assistant_id="a2", document_id="doc-2")
        store = self.scenario.vector_store
        self.assertEqual(
            {chunk.assistant_id.value for chunk in store.collections["assistant-a1-v1"].values()},
            {"a1"},
        )
        self.assertEqual(
            {chunk.assistant_id.value for chunk in store.collections["assistant-a2-v1"].values()},
            {"a2"},
        )

    def test_chunks_carry_section_model_and_pipeline_version(self) -> None:
        """CT-08: metadados por chunk."""
        self.scenario.ingest()
        chunks = sorted(
            self.scenario.vector_store.collections["assistant-a1-v1"].values(),
            key=lambda chunk: chunk.chunk_index,
        )
        self.assertEqual(chunks[0].id, "doc-1:0")
        self.assertEqual(chunks[0].section_path, "Politica de Ferias")
        self.assertEqual(
            chunks[-1].section_path,
            "Politica de Ferias > Estagiarios",
        )
        self.assertTrue(chunks[-1].text.startswith("Politica de Ferias > Estagiarios"))
        for chunk in chunks:
            self.assertEqual(chunk.embedding_model, MODEL)
            self.assertEqual(chunk.pipeline_version, PIPELINE_VERSION)
            self.assertEqual(chunk.source_name, "politica.md")
            self.assertIsNone(chunk.page)

    def test_document_records_model_version_count_and_original(self) -> None:
        """CT-08: registro por documento (RF-32)."""
        result = self.scenario.ingest()
        document = self.scenario.documents.items["doc-1"]
        self.assertEqual(document.embedding_model, MODEL)
        self.assertEqual(document.pipeline_version, PIPELINE_VERSION)
        self.assertEqual(document.chunk_count, result.chunk_count)
        self.assertEqual(document.metadata.values, {"origem": "teste"})
        self.assertEqual(document.status, DocumentStatus.INDEXED)
        self.assertEqual(document.size_bytes, len(MARKDOWN))
        self.assertEqual(document.uploaded_by, self.scenario.user.id)
        self.assertEqual(
            self.scenario.storage.load(document.storage_key or ""),
            MARKDOWN,
        )

    def test_file_at_the_limit_is_accepted(self) -> None:
        content = b"Texto. " + b"a" * (MAX_BYTES - 7)
        self.assertEqual(len(content), MAX_BYTES)
        self.scenario.ingest(source_name="grande.txt", raw_content=content)

    def test_file_above_the_limit_is_rejected_before_any_write(self) -> None:
        with self.assertRaises(DocumentTooLargeError):
            self.scenario.ingest(raw_content=b"a" * (MAX_BYTES + 1))
        self.assertEqual(self.scenario.documents.items, {})
        self.assertEqual(self.scenario.vector_store.collections, {})

    def test_empty_file_is_rejected_before_any_write(self) -> None:
        with self.assertRaises(ValueError):
            self.scenario.upload(source_name="vazio.txt", raw_content=b"")
        self.assertEqual(self.scenario.documents.items, {})
        self.assertEqual(self.scenario.queue.jobs, {})

    def test_file_without_text_fails_in_the_worker_without_retries(self) -> None:
        """C1: erro definitivo vai direto a ``falhou``."""
        outcome = self.scenario.ingest(source_name="vazio.txt", raw_content=b"   ")
        document = self.scenario.documents.items["doc-1"]
        self.assertEqual(outcome.status, "falhou")
        self.assertEqual(outcome.attempts, 1)
        self.assertEqual(document.status, DocumentStatus.FAILED)
        self.assertEqual(document.failure_reason, UNREADABLE_DOCUMENT_REASON)
        self.assertEqual(self.scenario.queue.pending(), [])
        self.assertEqual(
            self.scenario.vector_store.collections.get("assistant-a1-v1", {}), {}
        )

    def test_unsupported_format_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.scenario.upload(source_name="dados.csv", raw_content=b"a,b")
        self.assertEqual(self.scenario.queue.jobs, {})

    def test_file_without_extension_is_rejected(self) -> None:
        """O worker reconhece o formato pela extensao do nome."""
        with self.assertRaises(ValueError):
            self.scenario.upload(source_name="politica", raw_content=MARKDOWN)

    def test_ingestion_is_refused_while_base_is_from_the_mvp(self) -> None:
        """RN-16: base de outro modelo exige reindexacao antes."""
        self.scenario.add_legacy_base()
        with self.assertRaises(IndexOutdatedError):
            self.scenario.ingest()
        self.assertNotIn("doc-1", self.scenario.documents.items)

    def test_ingestion_is_refused_after_model_change(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        self.scenario.use_model("outro-modelo")
        with self.assertRaises(IndexOutdatedError):
            self.scenario.ingest(document_id="doc-2")

    def test_upload_during_reindex_waits_for_it_to_finish(self) -> None:
        """D8: o envio e aceito e o job so roda depois da troca do alias."""
        self.scenario.ingest(document_id="doc-1")
        job = self.scenario.start_reindex()
        self.scenario.upload(document_id="doc-2")
        self.assertIsNone(self.scenario.process())
        self.assertEqual(
            self.scenario.documents.items["doc-2"].status, DocumentStatus.PENDING
        )
        self.scenario.run_reindex(job.id)
        outcome = self.scenario.process()
        self.assertEqual(outcome.status, "indexado")
        target = self.scenario.vector_store.collections["assistant-a1-v2"]
        self.assertEqual(
            {chunk.document_id.value for chunk in target.values()},
            {"doc-1", "doc-2"},
        )


class StartReindexTestCase(IndexingTestCase):
    def test_targets_the_next_version(self) -> None:
        self.scenario.ingest()
        job = self.scenario.start_reindex()
        self.assertEqual(job.status, "running")
        self.assertEqual(job.target_collection, "assistant-a1-v2")
        self.assertEqual(job.total_documents, 1)

    def test_mvp_base_is_migrated_to_version_two(self) -> None:
        self.scenario.add_legacy_base()
        self.assertEqual(
            self.scenario.start_reindex().target_collection,
            "assistant-a1-v2",
        )

    def test_assistant_without_base_starts_at_version_one(self) -> None:
        self.assertEqual(
            self.scenario.start_reindex().target_collection,
            "assistant-a1-v1",
        )

    def test_second_reindex_is_refused_while_one_is_running(self) -> None:
        self.scenario.ingest()
        self.scenario.start_reindex()
        with self.assertRaises(ReindexInProgressError):
            self.scenario.start_reindex()

    def test_other_assistant_can_reindex_at_the_same_time(self) -> None:
        self.scenario.ingest(assistant_id="a1", document_id="doc-1")
        self.scenario.ingest(assistant_id="a2", document_id="doc-2")
        self.scenario.start_reindex("a1")
        self.assertEqual(self.scenario.start_reindex("a2").status, "running")


class RunReindexTestCase(IndexingTestCase):
    def test_success_swaps_alias_and_removes_previous_version(self) -> None:
        first = self.scenario.ingest(document_id="doc-1")
        second = self.scenario.ingest(document_id="doc-2")
        job = self.scenario.run_reindex(self.scenario.start_reindex().id)
        store = self.scenario.vector_store
        self.assertEqual(job.status, "succeeded")
        self.assertEqual(job.processed_documents, 2)
        self.assertIsNone(job.error)
        self.assertIsNotNone(job.finished_at)
        self.assertEqual(store.aliases, {"assistant-a1": "assistant-a1-v2"})
        self.assertEqual(list(store.collections), ["assistant-a1-v2"])
        self.assertEqual(
            len(store.collections["assistant-a1-v2"]),
            first.chunk_count + second.chunk_count,
        )

    def test_failure_keeps_current_collection_and_discards_partial(self) -> None:
        """CT-09: reindexacao com falha mantem a collection vigente."""
        self.scenario.ingest(document_id="doc-1")
        self.scenario.ingest(document_id="doc-2")
        store = self.scenario.vector_store
        before = dict(store.collections["assistant-a1-v1"])
        started = self.scenario.start_reindex()
        store.fail_upsert_into = "assistant-a1-v2"

        job = self.scenario.run_reindex(started.id)

        self.assertEqual(job.status, "failed")
        self.assertIn("vector store unavailable", job.error or "")
        self.assertEqual(store.aliases, {"assistant-a1": "assistant-a1-v1"})
        self.assertEqual(list(store.collections), ["assistant-a1-v1"])
        self.assertEqual(store.collections["assistant-a1-v1"], before)

    def test_missing_original_fails_and_keeps_current_collection(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        document = self.scenario.documents.items["doc-1"]
        self.scenario.documents.save(
            Document(
                id=document.id,
                assistant_id=document.assistant_id,
                source_name=document.source_name,
                content_hash=document.content_hash,
                embedding_model=document.embedding_model,
                pipeline_version=document.pipeline_version,
                chunk_count=document.chunk_count,
                storage_key="a1/nao-existe.md",
            )
        )
        job = self.scenario.run_reindex(self.scenario.start_reindex().id)
        self.assertEqual(job.status, "failed")
        self.assertEqual(
            self.scenario.vector_store.aliases,
            {"assistant-a1": "assistant-a1-v1"},
        )

    def test_count_mismatch_fails_the_reindex(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        started = self.scenario.start_reindex()
        self.scenario.vector_store.lose_points = True
        job = self.scenario.run_reindex(started.id)
        self.assertEqual(job.status, "failed")
        self.assertIn("chunk count mismatch", job.error or "")
        self.assertEqual(
            self.scenario.vector_store.aliases,
            {"assistant-a1": "assistant-a1-v1"},
        )

    def test_failed_reindex_can_be_started_again(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        started = self.scenario.start_reindex()
        self.scenario.vector_store.fail_upsert_into = "assistant-a1-v2"
        self.scenario.run_reindex(started.id)
        self.scenario.vector_store.fail_upsert_into = None
        job = self.scenario.run_reindex(self.scenario.start_reindex().id)
        self.assertEqual(job.status, "succeeded")
        self.assertEqual(job.target_collection, "assistant-a1-v2")

    def test_model_change_is_resolved_by_reindex(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        self.scenario.use_model("outro-modelo")
        self.assertTrue(self.scenario.status().outdated)

        self.scenario.run_reindex(self.scenario.start_reindex().id)

        status = self.scenario.status()
        self.assertFalse(status.outdated)
        self.assertEqual(status.embedding_model, "outro-modelo")
        self.assertEqual(
            self.scenario.documents.items["doc-1"].embedding_model,
            "outro-modelo",
        )
        chunk = next(
            iter(self.scenario.vector_store.collections["assistant-a1-v2"].values())
        )
        self.assertEqual(chunk.embedding_model, "outro-modelo")

    def test_mvp_base_is_replaced_and_alias_created(self) -> None:
        self.scenario.add_legacy_base()
        job = self.scenario.run_reindex(self.scenario.start_reindex().id)
        store = self.scenario.vector_store
        self.assertEqual(job.status, "succeeded")
        self.assertEqual(job.total_documents, 1)
        self.assertEqual(job.processed_documents, 0)
        self.assertEqual(store.aliases, {"assistant-a1": "assistant-a1-v2"})
        self.assertEqual(list(store.collections), ["assistant-a1-v2"])
        self.assertFalse(self.scenario.documents.items["legado"].is_indexed)
        # Com a base migrada, o novo upload volta a ser aceito.
        self.scenario.ingest(document_id="doc-1")
        self.assertFalse(self.scenario.status().outdated)

    def test_finished_job_is_not_run_again(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        started = self.scenario.start_reindex()
        self.scenario.run_reindex(started.id)
        again = self.scenario.run_reindex(started.id)
        self.assertEqual(again.status, "succeeded")
        self.assertEqual(
            list(self.scenario.vector_store.collections),
            ["assistant-a1-v2"],
        )

    def test_unknown_job_is_reported(self) -> None:
        with self.assertRaises(ReindexJobNotFoundError):
            self.scenario.run_reindex("nao-existe")


class ProcessNextReindexJobTestCase(IndexingTestCase):
    """PC-D4: o worker reserva e executa as reindexacoes pedidas pela API."""

    settings = ReindexSettings(max_attempts=2, lease_seconds=60)

    def _worker(self, run=None) -> ProcessNextReindexJobUseCase:
        scenario = self.scenario

        def run_reindex(job_id: str, lease: timedelta):
            return RunReindexUseCase(
                document_repository=scenario.documents,
                vector_store_gateway=scenario.vector_store,
                document_indexer=scenario.indexer,
                file_storage=scenario.storage,
                reindex_job_repository=scenario.jobs,
                permission_repository=scenario.access.permissions,
                lease=lease,
                clock=scenario.clock,
            ).execute(RunReindexInput(job_id=job_id))

        return ProcessNextReindexJobUseCase(
            reindex_job_repository=scenario.jobs,
            vector_store_gateway=scenario.vector_store,
            run_reindex=run or run_reindex,
            settings=self.settings,
            clock=scenario.clock,
        )

    def test_without_requested_reindex_there_is_nothing_to_do(self) -> None:
        self.assertIsNone(self._worker().execute())

    def test_requested_reindex_is_claimed_and_executed(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        started = self.scenario.start_reindex()
        self.assertEqual(started.status, "running")

        result = self._worker().execute()

        self.assertEqual(result.id, started.id)
        self.assertEqual(result.status, "succeeded")
        job = self.scenario.jobs.items[started.id]
        self.assertEqual(job.attempts, 1)
        self.assertIsNone(job.lease_expires_at)
        self.assertEqual(
            self.scenario.vector_store.aliases, {"assistant-a1": "assistant-a1-v2"}
        )
        self.assertIsNone(self._worker().execute())

    def test_claimed_job_is_not_claimed_again_before_the_lease_expires(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        started = self.scenario.start_reindex()
        claimed = self.scenario.jobs.claim_next(self.scenario.clock(), self.settings.lease)
        self.assertEqual(claimed.id, started.id)
        self.assertIsNone(self._worker().execute())

    def test_interrupted_reindex_is_resumed_from_scratch(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        started = self.scenario.start_reindex()
        # Worker interrompido: reservou, gravou parte da collection e parou.
        self.scenario.jobs.claim_next(self.scenario.clock(), self.settings.lease)
        self.scenario.vector_store.collections["assistant-a1-v2"] = {"lixo": object()}
        self.scenario.clock.advance(seconds=61)

        result = self._worker().execute()

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(self.scenario.jobs.items[started.id].attempts, 2)
        self.assertNotIn(
            "lixo", self.scenario.vector_store.collections["assistant-a1-v2"]
        )

    def test_progress_renews_the_lease(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        self.scenario.ingest(document_id="doc-2")
        started = self.scenario.start_reindex()
        leases: list = []
        jobs = self.scenario.jobs
        original_save = jobs.save

        def spy(job):
            leases.append(job.lease_expires_at)
            return original_save(job)

        jobs.save = spy
        self._worker().execute()
        self.assertTrue(any(lease is not None for lease in leases[:-1]))
        self.assertIsNone(jobs.items[started.id].lease_expires_at)

    def test_attempts_exhausted_fail_the_job_and_discard_the_partial(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        started = self.scenario.start_reindex()
        store = self.scenario.vector_store
        for _ in range(self.settings.max_attempts):
            self.scenario.jobs.claim_next(self.scenario.clock(), self.settings.lease)
            self.scenario.clock.advance(seconds=61)
        store.collections["assistant-a1-v2"] = {}
        calls: list[str] = []

        result = self._worker(run=lambda job_id, lease: calls.append(job_id)).execute()

        self.assertEqual(calls, [])
        self.assertEqual(result.status, "failed")
        self.assertIn("interrupted", result.error or "")
        job = self.scenario.jobs.items[started.id]
        self.assertEqual(job.status, ReindexStatus.FAILED)
        self.assertEqual(store.aliases, {"assistant-a1": "assistant-a1-v1"})
        self.assertEqual(list(store.collections), ["assistant-a1-v1"])
        self.assertEqual(self.scenario.start_reindex().status, "running")

    def test_abandoned_job_preserves_the_collection_already_in_use(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        self.scenario.start_reindex()
        store = self.scenario.vector_store
        store.collections["assistant-a1-v2"] = {}
        store.aliases["assistant-a1"] = "assistant-a1-v2"
        for _ in range(self.settings.max_attempts):
            self.scenario.jobs.claim_next(self.scenario.clock(), self.settings.lease)
            self.scenario.clock.advance(seconds=61)

        result = self._worker().execute()

        self.assertEqual(result.status, "failed")
        self.assertIn("assistant-a1-v2", store.collections)


class IndexStatusTestCase(IndexingTestCase):
    def test_assistant_without_documents(self) -> None:
        status = self.scenario.status()
        self.assertIsNone(status.collection_name)
        self.assertFalse(status.outdated)
        self.assertEqual(status.documents_total, 0)
        self.assertIsNone(status.last_reindex)
        self.assertEqual(status.embedding_model, MODEL)
        self.assertEqual(status.pipeline_version, PIPELINE_VERSION)

    def test_current_base(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        status = self.scenario.status()
        self.assertEqual(status.collection_name, "assistant-a1-v1")
        self.assertFalse(status.outdated)
        self.assertEqual(status.documents_total, 1)
        self.assertEqual(status.documents_indexed, 1)
        self.assertEqual(status.documents_without_original, ())

    def test_mvp_base_is_outdated_and_lists_documents_without_original(
        self,
    ) -> None:
        self.scenario.add_legacy_base()
        status = self.scenario.status()
        self.assertTrue(status.outdated)
        self.assertEqual(status.collection_name, "assistant-a1")
        self.assertEqual(status.documents_indexed, 0)
        self.assertEqual(status.documents_without_original, ("antigo.txt",))

    def test_reports_reindex_progress(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        started = self.scenario.start_reindex()
        running = self.scenario.status().last_reindex
        self.assertIsNotNone(running)
        self.assertEqual(running.status, "running")
        self.scenario.run_reindex(started.id)
        finished = self.scenario.status().last_reindex
        self.assertEqual(finished.status, "succeeded")
        self.assertEqual(finished.processed_documents, 1)


class LocalFileStorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.storage = LocalDocumentFileStorage(base_dir=directory.name)

    def _save(self, filename: str = "manual.PDF") -> str:
        return self.storage.save(
            assistant_id=AssistantId("a1"),
            document_id=DocumentId("doc-1"),
            filename=filename,
            content=b"conteudo",
        )

    def test_round_trip(self) -> None:
        self.assertEqual(self.storage.load(self._save()), b"conteudo")

    def test_key_uses_identifiers_and_extension_only(self) -> None:
        self.assertEqual(self._save("../../etc/segredo.PDF"), "a1/doc-1.pdf")

    def test_key_outside_base_directory_is_rejected(self) -> None:
        for key in ("../fora.txt", "/etc/passwd", "", "."):
            with self.assertRaises(ValueError):
                self.storage.load(key)

    def test_missing_file_is_reported(self) -> None:
        with self.assertRaises(FileNotFoundError):
            self.storage.load("a1/nao-existe.txt")


class LocalHashEmbeddingGatewayTestCase(unittest.TestCase):
    def test_implements_the_embedding_port_for_tests(self) -> None:
        gateway = LocalHashEmbeddingGateway(vector_size=16)
        documents = gateway.embed_documents(["ferias anuais", "reembolso"])
        self.assertEqual(gateway.dimension, 16)
        self.assertEqual(gateway.model_name, "local-hash")
        self.assertEqual(len(documents), 2)
        self.assertEqual(len(documents[0]), 16)
        self.assertEqual(gateway.embed_query("ferias anuais"), documents[0])


if __name__ == "__main__":
    unittest.main()
