from __future__ import annotations

from src.domain import ExtractedDocument

from .structured_extraction import PdfPageOcr, extract_supported_document
from .text_extraction import resolve_document_type


class SupportedDocumentExtractor:
    """Adaptador da porta ``DocumentExtractor`` para os formatos suportados.

    Com ``ocr``, paginas de PDF sem texto passam pelo OCR local (RF-53).
    """

    def __init__(self, *, ocr: PdfPageOcr | None = None) -> None:
        self._ocr = ocr

    def supports(self, *, filename: str | None, content_type: str | None) -> bool:
        return resolve_document_type(filename, content_type) is not None

    def extract(
        self,
        *,
        filename: str | None,
        content_type: str | None,
        raw_content: bytes,
    ) -> ExtractedDocument:
        return extract_supported_document(
            filename=filename,
            content_type=content_type,
            raw_content=raw_content,
            ocr=self._ocr,
        )
