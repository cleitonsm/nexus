import unittest
from unittest.mock import patch

from src.infrastructure.documents.text_extraction import (
    extract_supported_text,
    resolve_document_type,
)


class DocumentExtractionTestCase(unittest.TestCase):
    def test_extract_supported_text_accepts_plain_text(self) -> None:
        extracted = extract_supported_text(
            filename="knowledge.txt",
            content_type="text/plain",
            raw_content=b"  Conteudo de teste  ",
        )
        self.assertEqual(extracted, "Conteudo de teste")

    def test_extract_supported_text_rejects_unsupported_suffix(self) -> None:
        with self.assertRaises(ValueError):
            extract_supported_text(
                filename="arquivo.csv",
                content_type="text/csv",
                raw_content=b"value",
            )

    def test_resolve_type_uses_content_type_without_filename(self) -> None:
        resolved = resolve_document_type(
            filename=None,
            content_type="application/pdf",
        )
        self.assertEqual(resolved, ".pdf")

    def test_resolve_type_rejects_suffix_content_type_mismatch(self) -> None:
        resolved = resolve_document_type(
            filename="manual.pdf",
            content_type="text/plain",
        )
        self.assertIsNone(resolved)

    def test_extract_supported_text_dispatches_docx_extractor(self) -> None:
        with patch(
            "src.infrastructure.documents.text_extraction._EXTRACTORS",
            {".docx": lambda _: "Texto DOCX"},
        ):
            extracted = extract_supported_text(
                filename="manual.docx",
                content_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
                raw_content=b"fake-docx-binary",
            )
        self.assertEqual(extracted, "Texto DOCX")


if __name__ == "__main__":
    unittest.main()
