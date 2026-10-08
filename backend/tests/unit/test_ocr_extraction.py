"""OCR local de PDF digitalizado (SPEC-005, RF-53, RNF-26, D2).

O teste com o Tesseract real roda quando ``tesseract`` e ``pdftoppm`` estao
instalados (na imagem do backend estao); fora dela e ignorado.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
import unittest

from test_indexing import Scenario
from src.application.services import DocumentIndexer
from src.domain import BlockType
from src.infrastructure.embeddings import Bm25SparseEmbeddingGateway
from src.infrastructure.documents import (
    OcrUnavailableError,
    SupportedDocumentExtractor,
    TesseractPdfOcr,
    extract_supported_document,
)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - Pillow vem com o sentence-transformers
    Image = None  # type: ignore[assignment]

_TOOLS = shutil.which("tesseract") and shutil.which("pdftoppm")


def _installed_languages() -> set[str]:
    if not _TOOLS:
        return set()
    result = subprocess.run(
        ["tesseract", "--list-langs"], capture_output=True, check=False
    )
    lines = result.stdout.decode().splitlines()[1:]
    return {line.strip() for line in lines if line.strip()}


def _scanned_pdf(*lines: str) -> bytes:
    """PDF feito so de imagem, como o de um scanner: sem camada de texto."""
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    font = _font(48)
    for index, line in enumerate(lines):
        draw.text((100, 150 + index * 90), line, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PDF", resolution=150)
    return buffer.getvalue()


def _font(size: int):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


class FakeOcr:
    def __init__(self, text: str = "Texto reconhecido pelo OCR.") -> None:
        self.text = text
        self.pages: list[int] = []

    def recognize_page(self, pdf_content: bytes, page_number: int) -> str:
        self.pages.append(page_number)
        return self.text


@unittest.skipIf(Image is None, "Pillow indisponivel")
class OcrRoutingTestCase(unittest.TestCase):
    def test_page_without_text_goes_to_ocr(self) -> None:
        ocr = FakeOcr()
        document = extract_supported_document(
            filename="digitalizado.pdf",
            content_type="application/pdf",
            raw_content=_scanned_pdf("Politica de ferias"),
            ocr=ocr,
        )
        self.assertEqual(ocr.pages, [1])
        self.assertEqual(document.blocks[0].text, "Texto reconhecido pelo OCR.")
        self.assertEqual(document.blocks[0].page, 1)
        self.assertIs(document.blocks[0].type, BlockType.PARAGRAPH)

    def test_without_ocr_a_scanned_pdf_has_no_text(self) -> None:
        with self.assertRaises(ValueError):
            extract_supported_document(
                filename="digitalizado.pdf",
                content_type="application/pdf",
                raw_content=_scanned_pdf("Politica de ferias"),
            )

    def test_corrupted_pdf_is_a_definitive_error(self) -> None:
        """C1: ``ValueError`` leva o documento direto a ``falhou``."""
        with self.assertRaises(ValueError):
            SupportedDocumentExtractor(ocr=FakeOcr()).extract(
                filename="quebrado.pdf",
                content_type="application/pdf",
                raw_content=b"%PDF-1.4\n isto nao e um pdf",
            )


class OcrConfigurationTestCase(unittest.TestCase):
    def test_languages_must_use_tesseract_codes(self) -> None:
        self.assertEqual(TesseractPdfOcr().languages, "por+eng")
        for invalid in ("", "por eng", "por;rm -rf", "por+"):
            with self.subTest(languages=invalid), self.assertRaises(ValueError):
                TesseractPdfOcr(languages=invalid)

    def test_missing_programs_are_a_definitive_error(self) -> None:
        original = shutil.which
        try:
            shutil.which = lambda name: None  # type: ignore[assignment]
            with self.assertRaises(OcrUnavailableError):
                TesseractPdfOcr().recognize_page(b"%PDF", 1)
        finally:
            shutil.which = original  # type: ignore[assignment]
        self.assertTrue(issubclass(OcrUnavailableError, ValueError))


@unittest.skipIf(Image is None, "Pillow indisponivel")
@unittest.skipUnless("eng" in _installed_languages(), "Tesseract (eng) ausente")
class TesseractTestCase(unittest.TestCase):
    """Cenario "PDF digitalizado", com o OCR real."""

    def test_scanned_pdf_text_is_recognized_locally(self) -> None:
        extractor = SupportedDocumentExtractor(ocr=TesseractPdfOcr(languages="eng"))
        document = extractor.extract(
            filename="digitalizado.pdf",
            content_type="application/pdf",
            raw_content=_scanned_pdf(
                "Vacation policy",
                "Every employee is entitled",
                "to thirty days of vacation.",
            ),
        )
        text = " ".join(block.text for block in document.blocks).lower()
        self.assertIn("vacation policy", text)
        self.assertIn("thirty days", text)
        self.assertEqual({block.page for block in document.blocks}, {1})

    def test_scanned_pdf_reaches_indexed_through_the_worker(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        scenario = Scenario(directory.name)
        scenario.indexer = DocumentIndexer(
            extractor=SupportedDocumentExtractor(
                ocr=TesseractPdfOcr(languages="eng")
            ),
            chunker=scenario.indexer._chunker,
            embedding_gateway=scenario.embedding,
            sparse_embedding_gateway=Bm25SparseEmbeddingGateway(),
        )
        content = _scanned_pdf("Vacation policy", "Thirty days of vacation.")
        scenario.max_file_bytes = len(content)
        scenario.upload(source_name="digitalizado.pdf", raw_content=content)
        outcome = scenario.process()
        self.assertEqual(outcome.status, "indexado")
        self.assertGreaterEqual(outcome.chunk_count, 1)

    def test_unknown_language_is_a_definitive_error(self) -> None:
        with self.assertRaises(ValueError):
            TesseractPdfOcr(languages="xyzlang").recognize_page(
                _scanned_pdf("Texto"), 1
            )


if __name__ == "__main__":
    unittest.main()
