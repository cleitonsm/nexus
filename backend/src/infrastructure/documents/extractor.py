from __future__ import annotations

from src.domain import ExtractedDocument

from .structured_extraction import extract_supported_document


class SupportedDocumentExtractor:
    """Adaptador da porta ``DocumentExtractor`` para os formatos suportados."""

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
        )
