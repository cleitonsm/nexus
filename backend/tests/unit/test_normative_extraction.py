"""SPEC-20261026-012: estrutura normativa na extracao e no indexador (CT-91)."""

from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from chat_doubles import SingleVectorEmbeddingGateway, WordTokenCounter
from src.application.services import PIPELINE_VERSION, DocumentIndexer
from src.domain import AssistantId, DocumentId
from src.infrastructure.chunking import StructuralDocumentChunker
from src.infrastructure.documents import (
    SupportedDocumentExtractor,
    extract_supported_document,
)
from src.infrastructure.embeddings import Bm25SparseEmbeddingGateway

try:
    from docx import Document as DocxDocument
except ImportError:  # pragma: no cover
    DocxDocument = None

_DOCX_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
TITLE_ONE = "TÍTULO I - DAS DISPOSIÇÕES GERAIS"
CHAPTER_ONE = "CAPÍTULO I - Dos Prazos"

# Regulamento ficticio: cinco artigos, incisos, paragrafo unico e quebras de
# linha no meio das frases, como na extracao de um PDF.
REGULATION_LINES = [
    "REGULAMENTO INTERNO DA ASSOCIAÇÃO FICTÍCIA",
    "TÍTULO I",
    "DAS DISPOSIÇÕES GERAIS",
    "Art. 1º Este regulamento vale",
    "para todos os associados.",
    "Art. 2º Compete ao conselho:",
    "I - aprovar o plano anual;",
    "II - fiscalizar",
    "as contas;",
    "Parágrafo único. O conselho se reúne mensalmente.",
    "CAPÍTULO I",
    "Dos Prazos",
    "Art. 3º O prazo de recurso é de dez dias.",
    "Art. 4º O prazo conta em dias úteis.",
    "Art. 5º-A. O prazo dobra nas férias coletivas.",
]

EXPECTED = [
    ("REGULAMENTO INTERNO DA ASSOCIAÇÃO FICTÍCIA", ()),
    ("Este regulamento vale para todos os associados.", (TITLE_ONE, "Art. 1º")),
    ("Compete ao conselho:", (TITLE_ONE, "Art. 2º")),
    ("I - aprovar o plano anual;", (TITLE_ONE, "Art. 2º")),
    ("II - fiscalizar as contas;", (TITLE_ONE, "Art. 2º")),
    ("Parágrafo único. O conselho se reúne mensalmente.", (TITLE_ONE, "Art. 2º")),
    ("O prazo de recurso é de dez dias.", (TITLE_ONE, CHAPTER_ONE, "Art. 3º")),
    ("O prazo conta em dias úteis.", (TITLE_ONE, CHAPTER_ONE, "Art. 4º")),
    ("O prazo dobra nas férias coletivas.", (TITLE_ONE, CHAPTER_ONE, "Art. 5º-A")),
]


def _extract_pdf(pages: list[str]):
    with patch(
        "src.infrastructure.documents.structured_extraction._read_pdf_pages",
        return_value=pages,
    ):
        return extract_supported_document(
            filename="regulamento.pdf",
            content_type="application/pdf",
            raw_content=b"%PDF-fake",
        )


def _extract_text(text: str):
    return extract_supported_document(
        filename="regulamento.txt",
        content_type="text/plain",
        raw_content=text.encode("utf-8"),
    )


def _blocks(document) -> list[tuple[str, tuple[str, ...]]]:
    return [(block.text, block.section_path) for block in document.blocks]


class NormativePdfTestCase(unittest.TestCase):
    def test_structure_becomes_the_section_path(self) -> None:
        document = _extract_pdf(["\n".join(REGULATION_LINES)])
        self.assertEqual(_blocks(document), EXPECTED)

    def test_pages_are_kept_and_sections_cross_pages(self) -> None:
        document = _extract_pdf(
            ["\n".join(REGULATION_LINES[:7]), "\n".join(REGULATION_LINES[7:])]
        )
        self.assertEqual(_blocks(document), EXPECTED)
        pages = [block.page for block in document.blocks]
        self.assertEqual(pages, [1, 1, 1, 1, 2, 2, 2, 2, 2])

    def test_numbered_lines_are_not_headings_in_normative_mode(self) -> None:
        lines = REGULATION_LINES + ["1 Introdução"]
        document = _extract_pdf(["\n".join(lines)])
        self.assertEqual(
            document.blocks[-1].text, "O prazo dobra nas férias coletivas. 1 Introdução"
        )

    def test_below_the_threshold_the_pdf_is_parsed_as_before(self) -> None:
        lines = ["1 Introdução", "Conforme o regulamento:", "Art. 1º Texto um.", "Art. 2º Texto dois."]
        document = _extract_pdf(["\n".join(lines)])
        self.assertEqual(
            _blocks(document),
            [("Conforme o regulamento: Art. 1º Texto um. Art. 2º Texto dois.", ("Introdução",))],
        )


class NormativeTextTestCase(unittest.TestCase):
    def test_plain_text_uses_the_same_structure(self) -> None:
        document = _extract_text("\n".join(REGULATION_LINES))
        self.assertEqual(_blocks(document), EXPECTED)
        self.assertTrue(all(block.page is None for block in document.blocks))

    def test_blank_line_splits_blocks_inside_an_article(self) -> None:
        lines = REGULATION_LINES[:4] + ["", "para todos os associados."] + REGULATION_LINES[5:]
        document = _extract_text("\n".join(lines))
        self.assertEqual(document.blocks[1].text, "Este regulamento vale")
        self.assertEqual(document.blocks[2].text, "para todos os associados.")
        self.assertEqual(document.blocks[2].section_path, (TITLE_ONE, "Art. 1º"))

    def test_ordinary_text_is_unchanged(self) -> None:
        document = _extract_text("Linha um\nlinha dois\n\nArt. 1º sozinho.")
        self.assertEqual(
            _blocks(document),
            [("Linha um\nlinha dois", ()), ("Art. 1º sozinho.", ())],
        )


@unittest.skipIf(DocxDocument is None, "python-docx nao instalado")
class NormativeDocxTestCase(unittest.TestCase):
    def _extract(self, lines: list[str]):
        source = DocxDocument()
        for line in lines:
            source.add_paragraph(line)
        buffer = io.BytesIO()
        source.save(buffer)
        return extract_supported_document(
            filename="regulamento.docx",
            content_type=_DOCX_TYPE,
            raw_content=buffer.getvalue(),
        )

    def test_paragraphs_follow_the_normative_structure(self) -> None:
        lines = [line for line in REGULATION_LINES if line not in ("II - fiscalizar", "as contas;")]
        lines.insert(7, "II - fiscalizar as contas;")
        lines[3] = "Art. 1º Este regulamento vale para todos os associados."
        lines.remove("para todos os associados.")
        self.assertEqual(_blocks(self._extract(lines)), EXPECTED)


class NormativeIndexingTestCase(unittest.TestCase):
    """RF-83: o trecho leva o artigo e o prefixo com o ``Art. N``."""

    def setUp(self) -> None:
        self.indexer = DocumentIndexer(
            extractor=SupportedDocumentExtractor(),
            chunker=StructuralDocumentChunker(
                token_counter=WordTokenCounter(),
                max_tokens=24,
                overlap_sentences=1,
                max_prefix_tokens=8,
            ),
            embedding_gateway=SingleVectorEmbeddingGateway(),
            sparse_embedding_gateway=Bm25SparseEmbeddingGateway(),
        )

    def _chunks(self):
        return self.indexer.build_chunks(
            assistant_id=AssistantId("assistant-1"),
            document_id=DocumentId("doc-1"),
            source_name="regulamento.txt",
            content_type="text/plain",
            raw_content="\n".join(REGULATION_LINES).encode("utf-8"),
        )

    def test_pipeline_version_changes_with_the_new_metadata(self) -> None:
        self.assertEqual(PIPELINE_VERSION, "4")

    def test_chunks_carry_the_article_and_its_label(self) -> None:
        chunks = self._chunks()
        by_article = {chunk.legal_article for chunk in chunks}
        self.assertEqual(by_article, {None, "1", "2", "3", "4", "5-A"})
        for chunk in chunks:
            if chunk.legal_article is None:
                continue
            with self.subTest(chunk=chunk.chunk_index):
                label = chunk.section_path.split(" > ")[-1]
                self.assertTrue(label.startswith("Art. "))
                self.assertIn(label, chunk.text)

    def test_long_outer_titles_leave_the_article_in_the_prefix(self) -> None:
        article_two = [chunk for chunk in self._chunks() if chunk.legal_article == "2"]
        self.assertTrue(article_two)
        for chunk in article_two:
            self.assertTrue(chunk.text.startswith("Art. 2º"))


if __name__ == "__main__":
    unittest.main()
