import unittest

from src.domain import (
    AssistantId,
    BlockType,
    CollectionName,
    Document,
    DocumentBlock,
    DocumentChunk,
    DocumentId,
    DomainValidationError,
    ExtractedDocument,
    ReindexJob,
    ReindexStatus,
)


class DocumentBlockTestCase(unittest.TestCase):
    def test_block_keeps_section_and_page(self) -> None:
        block = DocumentBlock(
            type=BlockType.PARAGRAPH,
            text="  O reembolso ocorre em 10 dias.  ",
            section_path=("Politica", "Reembolso"),
            page=3,
        )
        self.assertEqual(block.text, "O reembolso ocorre em 10 dias.")
        self.assertEqual(block.section_path, ("Politica", "Reembolso"))
        self.assertEqual(block.page, 3)

    def test_block_rejects_empty_text(self) -> None:
        with self.assertRaises(DomainValidationError):
            DocumentBlock(type=BlockType.PARAGRAPH, text="   ")

    def test_block_rejects_page_below_one(self) -> None:
        with self.assertRaises(DomainValidationError):
            DocumentBlock(type=BlockType.PARAGRAPH, text="texto", page=0)

    def test_block_rejects_empty_section_title(self) -> None:
        with self.assertRaises(DomainValidationError):
            DocumentBlock(
                type=BlockType.PARAGRAPH,
                text="texto",
                section_path=("Politica", " "),
            )

    def test_header_lines_only_allowed_on_tables(self) -> None:
        with self.assertRaises(DomainValidationError):
            DocumentBlock(type=BlockType.PARAGRAPH, text="texto", header_lines=1)

    def test_header_lines_must_leave_at_least_one_row(self) -> None:
        with self.assertRaises(DomainValidationError):
            DocumentBlock(
                type=BlockType.TABLE,
                text="| a | b |\n|---|---|",
                header_lines=2,
            )

    def test_table_exposes_header_and_rows(self) -> None:
        block = DocumentBlock(
            type=BlockType.TABLE,
            text="| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |",
            header_lines=2,
        )
        self.assertEqual(block.header, "| a | b |\n|---|---|")
        self.assertEqual(block.rows, ("| 1 | 2 |", "| 3 | 4 |"))


class ExtractedDocumentTestCase(unittest.TestCase):
    def test_document_requires_at_least_one_block(self) -> None:
        with self.assertRaises(DomainValidationError):
            ExtractedDocument(blocks=())

    def test_plain_text_joins_blocks_in_order(self) -> None:
        document = ExtractedDocument(
            blocks=(
                DocumentBlock(type=BlockType.PARAGRAPH, text="Primeiro."),
                DocumentBlock(type=BlockType.PARAGRAPH, text="Segundo."),
            )
        )
        self.assertEqual(document.plain_text, "Primeiro.\n\nSegundo.")


class DocumentChunkTestCase(unittest.TestCase):
    def test_chunk_rejects_negative_index(self) -> None:
        with self.assertRaises(DomainValidationError):
            DocumentChunk(index=-1, text="texto")

    def test_chunk_rejects_empty_text(self) -> None:
        with self.assertRaises(DomainValidationError):
            DocumentChunk(index=0, text=" ")

    def test_chunk_formats_section_path(self) -> None:
        chunk = DocumentChunk(
            index=0,
            text="texto",
            section_path=("Politica de Ferias", "Estagiarios"),
            page=2,
        )
        self.assertEqual(chunk.section_label, "Politica de Ferias > Estagiarios")


class VersionedCollectionNameTestCase(unittest.TestCase):
    def test_versioned_name_appends_version_to_alias(self) -> None:
        assistant_id = AssistantId("Assistente Principal")
        alias = CollectionName.from_assistant_id(assistant_id)
        versioned = CollectionName.versioned(assistant_id, 2)
        self.assertEqual(versioned.value, "assistant-assistente-principal-v2")
        self.assertEqual(versioned.value, f"{alias.value}-v2")

    def test_versioned_name_rejects_version_below_one(self) -> None:
        with self.assertRaises(DomainValidationError):
            CollectionName.versioned(AssistantId("a1"), 0)

    def test_version_is_read_from_versioned_name(self) -> None:
        assistant_id = AssistantId("a1")
        self.assertEqual(CollectionName.versioned(assistant_id, 12).version, 12)
        self.assertIsNone(CollectionName.from_assistant_id(assistant_id).version)


def _document(**fields: object) -> Document:
    return Document(
        id=DocumentId("doc-1"),
        assistant_id=AssistantId("a1"),
        source_name="manual.md",
        content_hash="hash",
        **fields,
    )


class DocumentIndexingStateTestCase(unittest.TestCase):
    def test_document_from_the_mvp_is_not_indexed(self) -> None:
        document = _document()
        self.assertFalse(document.is_indexed)
        self.assertFalse(document.has_original)
        self.assertEqual(document.chunk_count, 0)

    def test_is_current_requires_same_model_and_pipeline(self) -> None:
        document = _document(embedding_model="m1", pipeline_version="2")
        self.assertTrue(
            document.is_current(embedding_model="m1", pipeline_version="2")
        )
        self.assertFalse(
            document.is_current(embedding_model="m2", pipeline_version="2")
        )
        self.assertFalse(
            document.is_current(embedding_model="m1", pipeline_version="3")
        )

    def test_indexed_with_returns_updated_copy(self) -> None:
        original = _document(storage_key="a1/doc-1.md")
        updated = original.indexed_with(
            embedding_model="m1",
            pipeline_version="2",
            chunk_count=7,
        )
        self.assertFalse(original.is_indexed)
        self.assertEqual(updated.chunk_count, 7)
        self.assertEqual(updated.storage_key, "a1/doc-1.md")
        self.assertEqual(updated.created_at, original.created_at)

    def test_negative_chunk_count_is_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            _document(chunk_count=-1)


class ReindexJobTestCase(unittest.TestCase):
    def _job(self) -> ReindexJob:
        return ReindexJob(
            id="job-1",
            assistant_id=AssistantId("a1"),
            target_collection="assistant-a1-v2",
            total_documents=3,
        )

    def test_new_job_is_running(self) -> None:
        job = self._job()
        self.assertTrue(job.is_running)
        self.assertIsNone(job.finished_at)

    def test_progress_keeps_job_running(self) -> None:
        job = self._job().with_progress(total=3, processed=2)
        self.assertEqual(job.processed_documents, 2)
        self.assertTrue(job.is_running)

    def test_succeed_closes_the_job(self) -> None:
        job = self._job().succeed()
        self.assertEqual(job.status, ReindexStatus.SUCCEEDED)
        self.assertIsNotNone(job.finished_at)
        self.assertFalse(job.is_running)

    def test_fail_records_the_error(self) -> None:
        job = self._job().fail("  qdrant indisponivel  ")
        self.assertEqual(job.status, ReindexStatus.FAILED)
        self.assertEqual(job.error, "qdrant indisponivel")
        self.assertIsNotNone(job.finished_at)

    def test_empty_target_collection_is_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            ReindexJob(
                id="job-1",
                assistant_id=AssistantId("a1"),
                target_collection=" ",
            )

    def test_negative_counters_are_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            ReindexJob(
                id="job-1",
                assistant_id=AssistantId("a1"),
                target_collection="assistant-a1-v2",
                processed_documents=-1,
            )


if __name__ == "__main__":
    unittest.main()
