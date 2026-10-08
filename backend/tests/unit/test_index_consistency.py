"""R18, PC-D3: conferencia de contagens PostgreSQL x Qdrant."""

from __future__ import annotations

import logging
import tempfile
import unittest
from dataclasses import dataclass, replace

from test_indexing import Scenario

from src.application.use_cases import CheckIndexConsistencyUseCase
from src.application.use_cases.check_consistency import (
    SKIPPED_LEGACY,
    SKIPPED_REINDEXING,
)
from src.domain import AssistantId, DocumentId, DocumentStatus


@dataclass(frozen=True)
class _Assistant:
    id: AssistantId


class InMemoryAssistants:
    def __init__(self, *ids: str) -> None:
        self._items = [_Assistant(AssistantId(value)) for value in ids]

    def list_all(self) -> list[_Assistant]:
        return list(self._items)


class ConsistencyCheckTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.scenario = Scenario(directory.name)
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)

    def check(self, *assistants: str, only: str | None = None):
        s = self.scenario
        return CheckIndexConsistencyUseCase(
            assistant_repository=InMemoryAssistants(*(assistants or ("a1",))),
            document_repository=s.documents,
            vector_store_gateway=s.vector_store,
            reindex_job_repository=s.jobs,
        ).execute(only)

    def points(self) -> dict:
        return self.scenario.vector_store.collections["assistant-a1-v1"]

    def test_indexed_base_is_consistent(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        self.scenario.ingest(document_id="doc-2")
        report = self.check()
        self.assertTrue(report.consistent)
        self.assertEqual(report.assistants[0].documents_checked, 2)
        self.assertEqual(report.assistants[0].collection_name, "assistant-a1-v1")

    def test_point_removed_by_hand_is_reported(self) -> None:
        """CT-57 (nivel unitario): ponto apagado no Qdrant aparece como divergencia."""
        result = self.scenario.ingest(document_id="doc-1")
        first_point = next(iter(self.points()))
        del self.points()[first_point]

        report = self.check()

        self.assertFalse(report.consistent)
        divergence = report.assistants[0].divergences[0]
        self.assertEqual(divergence.document_id, "doc-1")
        self.assertEqual(divergence.expected, result.chunk_count)
        self.assertEqual(divergence.found, result.chunk_count - 1)
        self.assertEqual(report.divergence_count, 1)

    def test_points_of_unknown_document_are_orphans(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        self.scenario.documents.delete(DocumentId("doc-1"))
        report = self.check()
        self.assertFalse(report.consistent)
        orphan_id, count = report.assistants[0].orphan_documents[0]
        self.assertEqual(orphan_id, "doc-1")
        self.assertGreater(count, 0)

    def test_failed_document_must_have_no_points(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        document = self.scenario.documents.get_by_id(DocumentId("doc-1"))
        self.scenario.documents.items["doc-1"] = replace(
            document, status=DocumentStatus.FAILED
        )
        divergence = self.check().assistants[0].divergences[0]
        self.assertEqual(divergence.status, "falhou")
        self.assertEqual(divergence.expected, 0)

    def test_points_left_by_a_replaced_version_are_orphans(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        document = self.scenario.documents.get_by_id(DocumentId("doc-1"))
        self.scenario.documents.items["doc-1"] = replace(
            document, status=DocumentStatus.REPLACED
        )
        item = self.check().assistants[0]
        self.assertEqual(item.orphan_documents[0][0], "doc-1")

    def test_documents_in_progress_are_left_out(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        self.scenario.upload(document_id="doc-2")
        report = self.check()
        self.assertTrue(report.consistent)
        self.assertEqual(report.assistants[0].documents_checked, 1)

    def test_assistant_in_reindex_is_skipped(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        self.scenario.start_reindex()
        item = self.check().assistants[0]
        self.assertEqual(item.skipped_reason, SKIPPED_REINDEXING)
        self.assertTrue(item.consistent)

    def test_mvp_base_is_skipped(self) -> None:
        self.scenario.add_legacy_base()
        item = self.check().assistants[0]
        self.assertEqual(item.skipped_reason, SKIPPED_LEGACY)

    def test_indexed_document_without_collection_is_reported(self) -> None:
        self.scenario.ingest(document_id="doc-1")
        store = self.scenario.vector_store
        store.collections.clear()
        store.aliases.clear()
        divergence = self.check().assistants[0].divergences[0]
        self.assertEqual(divergence.found, 0)

    def test_single_assistant_can_be_checked(self) -> None:
        self.scenario.ingest(assistant_id="a1", document_id="doc-1")
        self.scenario.ingest(assistant_id="a2", document_id="doc-2")
        report = self.check("a1", "a2", only="a2")
        self.assertEqual([item.assistant_id for item in report.assistants], ["a2"])


if __name__ == "__main__":
    unittest.main()
