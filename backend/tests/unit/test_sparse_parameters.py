"""PC-D2: mudanca de ``BM25_*`` sem reindexar e detectada e so avisa."""

from __future__ import annotations

import logging
import tempfile
import unittest
from dataclasses import dataclass

from test_indexing import Scenario

from src.application.services import DocumentIndexer
from src.application.use_cases import (
    GetIndexStatusInput,
    GetIndexStatusUseCase,
    ProcessNextIngestionJobUseCase,
    ReportSparseParameterChangesUseCase,
    RunReindexInput,
    RunReindexUseCase,
    StartReindexInput,
    StartReindexUseCase,
)
from src.domain import (
    AssistantId,
    CollectionName,
    DomainValidationError,
    SparseEncodingParameters,
)
from src.infrastructure.chunking import StructuralDocumentChunker
from src.infrastructure.documents import SupportedDocumentExtractor
from src.infrastructure.embeddings import Bm25SparseEmbeddingGateway

DEFAULTS = SparseEncodingParameters(k1=1.2, b=0.75, average_length=64.0)
CHANGED = SparseEncodingParameters(k1=1.5, b=0.75, average_length=64.0)


class InMemoryIndexParameters:
    def __init__(self) -> None:
        self.items: dict[str, SparseEncodingParameters] = {}

    def get_sparse_parameters(
        self, collection_name: CollectionName
    ) -> SparseEncodingParameters | None:
        return self.items.get(collection_name.value)

    def save_sparse_parameters(
        self,
        collection_name: CollectionName,
        parameters: SparseEncodingParameters,
    ) -> None:
        self.items[collection_name.value] = parameters


@dataclass(frozen=True)
class _Assistant:
    id: AssistantId


class InMemoryAssistants:
    def __init__(self, *ids: str) -> None:
        self._items = [_Assistant(AssistantId(value)) for value in ids]

    def list_all(self) -> list[_Assistant]:
        return list(self._items)


class CountingMetrics:
    def __init__(self) -> None:
        self.counters: dict[str, float] = {}

    def increment(self, name, value=1.0, labels=None) -> None:
        self.counters[name] = self.counters.get(name, 0.0) + value

    def observe(self, name, value, labels=None) -> None:
        pass


def _indexer(scenario: Scenario, parameters: SparseEncodingParameters) -> DocumentIndexer:
    from test_indexing import WordTokenCounter

    return DocumentIndexer(
        extractor=SupportedDocumentExtractor(),
        chunker=StructuralDocumentChunker(
            token_counter=WordTokenCounter(),
            max_tokens=24,
            overlap_sentences=1,
            max_prefix_tokens=8,
        ),
        embedding_gateway=scenario.embedding,
        sparse_embedding_gateway=Bm25SparseEmbeddingGateway(
            k1=parameters.k1,
            b=parameters.b,
            average_length=parameters.average_length,
        ),
    )


class SparseParametersTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.scenario = Scenario(directory.name)
        self.repository = InMemoryIndexParameters()
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)

    def process(self, indexer: DocumentIndexer | None = None):
        s = self.scenario
        return ProcessNextIngestionJobUseCase(
            job_queue=s.queue,
            document_repository=s.documents,
            vector_store_gateway=s.vector_store,
            document_indexer=indexer or s.indexer,
            file_storage=s.storage,
            reindex_job_repository=s.jobs,
            access_control=s.access.control,
            clock=s.clock,
            index_parameters=self.repository,
        ).execute()

    def ingest(self, assistant_id: str = "a1", document_id: str = "doc-1"):
        self.scenario.upload(assistant_id=assistant_id, document_id=document_id)
        return self.process()

    def status(self, current: SparseEncodingParameters, assistant_id: str = "a1"):
        s = self.scenario
        return GetIndexStatusUseCase(
            document_repository=s.documents,
            vector_store_gateway=s.vector_store,
            embedding_gateway=s.embedding,
            reindex_job_repository=s.jobs,
            access_control=s.access.control,
            index_parameters=self.repository,
            sparse_parameters=current,
        ).execute(GetIndexStatusInput(user=s.user, assistant_id=assistant_id))

    def reindex(self, indexer: DocumentIndexer, assistant_id: str = "a1"):
        s = self.scenario
        job = StartReindexUseCase(
            document_repository=s.documents,
            vector_store_gateway=s.vector_store,
            reindex_job_repository=s.jobs,
            access_control=s.access.control,
        ).execute(StartReindexInput(user=s.user, assistant_id=assistant_id))
        return RunReindexUseCase(
            document_repository=s.documents,
            vector_store_gateway=s.vector_store,
            document_indexer=indexer,
            file_storage=s.storage,
            reindex_job_repository=s.jobs,
            permission_repository=s.access.permissions,
            index_parameters=self.repository,
        ).execute(RunReindexInput(job_id=job.id))


class RecordingTestCase(SparseParametersTestCase):
    def test_first_collection_records_the_current_parameters(self) -> None:
        self.ingest()
        self.assertEqual(self.repository.items, {"assistant-a1-v1": DEFAULTS})

    def test_reindex_records_the_parameters_of_the_new_version(self) -> None:
        self.ingest()
        result = self.reindex(_indexer(self.scenario, CHANGED))
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(self.repository.items["assistant-a1-v2"], CHANGED)
        self.assertEqual(self.repository.items["assistant-a1-v1"], DEFAULTS)


class StatusTestCase(SparseParametersTestCase):
    def test_same_parameters_are_not_flagged(self) -> None:
        self.ingest()
        status = self.status(DEFAULTS)
        self.assertFalse(status.sparse_parameters_changed)
        self.assertEqual(status.sparse_parameters_recorded, DEFAULTS.as_dict())

    def test_changed_parameters_are_flagged_and_logged(self) -> None:
        self.ingest()
        logging.disable(logging.NOTSET)
        with self.assertLogs(
            "src.application.use_cases.reindex_assistant", level="WARNING"
        ) as logs:
            status = self.status(CHANGED)
        self.assertTrue(status.sparse_parameters_changed)
        self.assertEqual(status.sparse_parameters_recorded, DEFAULTS.as_dict())
        self.assertEqual(status.sparse_parameters_current, CHANGED.as_dict())
        self.assertIn("index.sparse_parameters_changed", logs.output[0])

    def test_change_only_warns_and_does_not_block_uploads(self) -> None:
        self.ingest()
        status = self.status(CHANGED)
        self.assertTrue(status.sparse_parameters_changed)
        self.assertFalse(status.outdated)
        self.scenario.upload(document_id="doc-2")
        outcome = self.process(_indexer(self.scenario, CHANGED))
        self.assertEqual(outcome.status, "indexado")

    def test_reindex_with_current_parameters_clears_the_flag(self) -> None:
        self.ingest()
        self.reindex(_indexer(self.scenario, CHANGED))
        self.assertFalse(self.status(CHANGED).sparse_parameters_changed)

    def test_collection_without_record_is_not_flagged(self) -> None:
        self.ingest()
        self.repository.items.clear()
        status = self.status(CHANGED)
        self.assertFalse(status.sparse_parameters_changed)
        self.assertIsNone(status.sparse_parameters_recorded)

    def test_assistant_without_collection_is_not_flagged(self) -> None:
        self.assertFalse(self.status(CHANGED, assistant_id="a1").sparse_parameters_changed)


class StartupReportTestCase(SparseParametersTestCase):
    def test_reports_only_assistants_with_changed_parameters(self) -> None:
        self.ingest(assistant_id="a1")
        self.ingest(assistant_id="a2", document_id="doc-2")
        self.repository.items["assistant-a2-v1"] = CHANGED
        metrics = CountingMetrics()
        changed = ReportSparseParameterChangesUseCase(
            assistant_repository=InMemoryAssistants("a1", "a2", "a3"),
            vector_store_gateway=self.scenario.vector_store,
            index_parameters=self.repository,
            sparse_parameters=DEFAULTS,
            metrics=metrics,
        ).execute()
        self.assertEqual(changed, ["a2"])
        self.assertEqual(
            metrics.counters, {"nexus_index_sparse_parameters_changed_total": 1.0}
        )


class SparseEncodingParametersTestCase(unittest.TestCase):
    def test_gateway_exposes_its_parameters(self) -> None:
        gateway = Bm25SparseEmbeddingGateway(k1=1.5, b=0.5, average_length=80.0)
        self.assertEqual(
            gateway.parameters,
            SparseEncodingParameters(k1=1.5, b=0.5, average_length=80.0),
        )

    def test_matches_tolerates_float_noise_only(self) -> None:
        self.assertTrue(
            DEFAULTS.matches(
                SparseEncodingParameters(k1=1.2 + 1e-12, b=0.75, average_length=64.0)
            )
        )
        self.assertFalse(DEFAULTS.matches(CHANGED))

    def test_invalid_parameters_are_rejected(self) -> None:
        for k1, b, average_length in ((-0.1, 0.75, 64.0), (1.2, 1.5, 64.0), (1.2, 0.75, 0.0)):
            with self.subTest(k1=k1, b=b, average_length=average_length):
                with self.assertRaises(DomainValidationError):
                    SparseEncodingParameters(k1=k1, b=b, average_length=average_length)


if __name__ == "__main__":
    unittest.main()
