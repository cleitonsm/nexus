from __future__ import annotations

import io
import re
from typing import Callable, Iterator, Protocol

from src.domain import BlockType, DocumentBlock, ExtractedDocument

from .text_extraction import (
    _extract_doc_text,
    _extract_plain_text,
    resolve_document_type,
)

_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
_FENCE = re.compile(r"^ {0,3}(```|~~~)")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$")
_RULE = re.compile(r"^ {0,3}([-*_])(?:\s*\1){2,}\s*$")
_QUOTE = re.compile(r"^ {0,3}>\s?")

_DOCX_HEADING_STYLE = re.compile(r"^(?:heading|t[ií]tulo)\s*(\d)$", re.IGNORECASE)
_DOCX_LIST_STYLE = re.compile(r"^list", re.IGNORECASE)

# Heuristica de titulo em PDF (decisao D2 da SPEC-002): linha curta e numerada,
# como "1 Introducao" ou "2.1 Escopo", sem pontuacao final.
_PDF_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+([^\W\d_].*)$")
_PDF_HEADING_MAX_WORDS = 12
_SENTENCE_END = ".;:,!?"


class PdfPageOcr(Protocol):
    """Reconhece o texto de uma pagina de PDF sem camada de texto (RF-53)."""

    def recognize_page(self, pdf_content: bytes, page_number: int) -> str: ...


def extract_supported_document(
    *,
    filename: str | None,
    content_type: str | None,
    raw_content: bytes,
    ocr: PdfPageOcr | None = None,
) -> ExtractedDocument:
    """``ocr`` trata as paginas de PDF sem texto; sem ele, elas ficam vazias."""
    document_type = resolve_document_type(filename, content_type)
    if document_type is None:
        raise ValueError(
            "unsupported file format. Supported formats: "
            ".txt, .md, .markdown, .pdf, .doc, .docx"
        )
    if not raw_content:
        raise ValueError("uploaded file is empty.")

    if document_type == ".pdf":
        blocks = _parse_pdf_pages(_read_pdf_pages(raw_content, ocr))
    else:
        blocks = _BLOCK_EXTRACTORS[document_type](raw_content)
    if not blocks:
        raise ValueError("uploaded file does not contain text content.")
    return ExtractedDocument(blocks=tuple(blocks))


class _SectionStack:
    """Mantem o caminho de titulos conforme os niveis encontrados."""

    def __init__(self) -> None:
        self._entries: list[tuple[int, str]] = []

    def enter(self, level: int, title: str) -> None:
        while self._entries and self._entries[-1][0] >= level:
            self._entries.pop()
        self._entries.append((level, title))

    @property
    def path(self) -> tuple[str, ...]:
        return tuple(title for _, title in self._entries)


class _BlockBuilder:
    """Acumula linhas de um bloco e o emite com a secao vigente."""

    def __init__(self, sections: _SectionStack) -> None:
        self._sections = sections
        self._kind: BlockType | None = None
        self._lines: list[str] = []
        self.blocks: list[DocumentBlock] = []
        self.page: int | None = None

    @property
    def kind(self) -> BlockType | None:
        return self._kind

    def add(self, kind: BlockType, line: str) -> None:
        if self._kind is not kind:
            self.flush()
            self._kind = kind
        self._lines.append(line)

    def start(self, kind: BlockType, line: str) -> None:
        self.flush()
        self.add(kind, line)

    def flush(self) -> None:
        kind, lines = self._kind, self._lines
        self._kind, self._lines = None, []
        if kind is None:
            return
        text = _join_lines(kind, lines)
        if not text.strip():
            return
        self.blocks.append(
            DocumentBlock(
                type=kind,
                text=text,
                section_path=self._sections.path,
                page=self.page,
                header_lines=_table_header_lines(kind, lines),
            )
        )


def _join_lines(kind: BlockType, lines: list[str]) -> str:
    if kind in (BlockType.TABLE, BlockType.CODE):
        return "\n".join(line.rstrip() for line in lines)
    return " ".join(line.strip() for line in lines if line.strip())


def _table_header_lines(kind: BlockType, lines: list[str]) -> int:
    if kind is not BlockType.TABLE or len(lines) < 3:
        return 0
    return 2 if _TABLE_SEPARATOR.match(lines[1]) else 0


def _parse_markdown(text: str) -> list[DocumentBlock]:
    sections = _SectionStack()
    builder = _BlockBuilder(sections)
    fence: str | None = None
    for raw_line in text.splitlines():
        if fence is not None:
            if raw_line.strip().startswith(fence):
                fence = None
                builder.flush()
            else:
                builder.add(BlockType.CODE, raw_line)
            continue
        fence_match = _FENCE.match(raw_line)
        if fence_match:
            builder.flush()
            fence = fence_match.group(1)
            continue
        _parse_markdown_line(_QUOTE.sub("", raw_line), builder, sections)
    builder.flush()
    return builder.blocks


def _parse_markdown_line(
    line: str,
    builder: _BlockBuilder,
    sections: _SectionStack,
) -> None:
    if not line.strip() or _RULE.match(line):
        builder.flush()
        return
    heading = _HEADING.match(line)
    if heading:
        builder.flush()
        if heading.group(2).strip():
            sections.enter(len(heading.group(1)), heading.group(2).strip())
        return
    if _TABLE_ROW.match(line):
        builder.add(BlockType.TABLE, line.strip())
    elif _LIST_ITEM.match(line):
        builder.start(BlockType.LIST_ITEM, line)
    elif builder.kind is BlockType.LIST_ITEM:
        builder.add(BlockType.LIST_ITEM, line)
    else:
        builder.add(BlockType.PARAGRAPH, line)


def _parse_plain_text(text: str) -> list[DocumentBlock]:
    blocks: list[DocumentBlock] = []
    for paragraph in re.split(r"\n\s*\n", text):
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if lines:
            blocks.append(
                DocumentBlock(type=BlockType.PARAGRAPH, text="\n".join(lines))
            )
    return blocks


def _parse_pdf_pages(pages: list[str]) -> list[DocumentBlock]:
    sections = _SectionStack()
    builder = _BlockBuilder(sections)
    for page_number, page_text in enumerate(pages, start=1):
        builder.flush()
        builder.page = page_number
        for line in page_text.splitlines():
            _parse_pdf_line(line.strip(), builder, sections)
    builder.flush()
    return builder.blocks


def _parse_pdf_line(
    line: str,
    builder: _BlockBuilder,
    sections: _SectionStack,
) -> None:
    if not line:
        builder.flush()
        return
    heading = _pdf_heading(line)
    if heading is None:
        builder.add(BlockType.PARAGRAPH, line)
        return
    builder.flush()
    sections.enter(*heading)


def _pdf_heading(line: str) -> tuple[int, str] | None:
    match = _PDF_HEADING.match(line)
    if match is None or line[-1] in _SENTENCE_END:
        return None
    title = match.group(2).strip()
    if len(line.split()) > _PDF_HEADING_MAX_WORDS or not title[0].isupper():
        return None
    return match.group(1).count(".") + 1, title


def _read_pdf_pages(
    raw_content: bytes,
    ocr: PdfPageOcr | None = None,
) -> list[str]:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
        from pypdf.errors import PyPdfError  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pypdf dependency is required to process PDF files."
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(raw_content))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except PyPdfError as exc:
        # Arquivo corrompido: nenhuma nova tentativa o tornaria legivel (C1).
        raise ValueError(f"could not read the PDF file: {exc}") from exc
    if ocr is None:
        return pages
    # Pagina digitalizada: so imagem, nenhum caractere na camada de texto.
    return [
        text if text.strip() else ocr.recognize_page(raw_content, number)
        for number, text in enumerate(pages, start=1)
    ]


def _parse_docx(raw_content: bytes) -> list[DocumentBlock]:
    sections = _SectionStack()
    blocks: list[DocumentBlock] = []
    for kind, text, style_name in _iter_docx_items(raw_content):
        if not text.strip():
            continue
        level = _docx_heading_level(style_name)
        if kind is BlockType.PARAGRAPH and level is not None:
            sections.enter(level, text.strip())
            continue
        rows = text.count("\n") + 1
        blocks.append(
            DocumentBlock(
                type=kind,
                text=text,
                section_path=sections.path,
                header_lines=1 if kind is BlockType.TABLE and rows > 1 else 0,
            )
        )
    return blocks


def _iter_docx_items(
    raw_content: bytes,
) -> Iterator[tuple[BlockType, str, str]]:
    try:
        from docx import (  # type: ignore[import-not-found]
            Document as DocxDocument,
        )
        from docx.table import Table  # type: ignore[import-not-found]
        from docx.text.paragraph import (  # type: ignore[import-not-found]
            Paragraph,
        )
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "python-docx dependency is required to process DOCX files."
        ) from exc

    document = DocxDocument(io.BytesIO(raw_content))
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            paragraph = Paragraph(child, document)
            style_name = paragraph.style.name if paragraph.style else ""
            kind = _docx_paragraph_kind(paragraph, style_name)
            yield kind, paragraph.text, style_name
        elif child.tag.endswith("}tbl"):
            yield BlockType.TABLE, _docx_table_text(Table(child, document)), ""


def _docx_paragraph_kind(paragraph: object, style_name: str) -> BlockType:
    properties = getattr(getattr(paragraph, "_p", None), "pPr", None)
    numbered = getattr(properties, "numPr", None) is not None
    if numbered or _DOCX_LIST_STYLE.match(style_name or ""):
        return BlockType.LIST_ITEM
    return BlockType.PARAGRAPH


def _docx_heading_level(style_name: str) -> int | None:
    normalized = (style_name or "").strip()
    if normalized.lower() == "title":
        return 1
    match = _DOCX_HEADING_STYLE.match(normalized)
    return int(match.group(1)) if match else None


def _docx_table_text(table: object) -> str:
    rows: list[str] = []
    for row in table.rows:  # type: ignore[attr-defined]
        cells = [" ".join(cell.text.split()) for cell in row.cells]
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _markdown_blocks(raw_content: bytes) -> list[DocumentBlock]:
    return _parse_markdown(_extract_plain_text(raw_content))


def _plain_blocks(raw_content: bytes) -> list[DocumentBlock]:
    return _parse_plain_text(_extract_plain_text(raw_content))


def _doc_blocks(raw_content: bytes) -> list[DocumentBlock]:
    return _parse_plain_text(_extract_doc_text(raw_content))


_BLOCK_EXTRACTORS: dict[str, Callable[[bytes], list[DocumentBlock]]] = {
    ".txt": _plain_blocks,
    ".md": _markdown_blocks,
    ".markdown": _markdown_blocks,
    ".docx": _parse_docx,
    ".doc": _doc_blocks,
}
