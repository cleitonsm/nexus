import unittest

from src.domain import (
    AssistantId,
    BlockType,
    CollectionName,
    DocumentBlock,
    DocumentChunk,
    DomainValidationError,
    ExtractedDocument,
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


if __name__ == "__main__":
    unittest.main()
