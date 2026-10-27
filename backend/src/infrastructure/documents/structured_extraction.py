from __future__ import annotations

import io
import re
from typing import Callable, Iterator, Protocol

from src.domain import (
    BlockType,
    DocumentBlock,
    ExtractedDocument,
    UnreadableDocumentError,
    is_normative,
    starts_legal_item,
    structural_heading,
)
from src.domain.legal_references import ARTICLE_LEVEL

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

# SPEC-012 (D4): linha logo abaixo de "TITULO II" que o nomeia, como "DOS
# DIREITOS E GARANTIAS FUNDAMENTAIS" ou "Dos Prazos".
_SUBTITLE_START = re.compile(r"^D[aeo]s?\s")
_SUBTITLE_MAX_WORDS = 15


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
        pages = _read_pdf_pages(raw_content, ocr)
        if _normative_pages(pages):
            blocks = _parse_normative_pages(pages)
        else:
            blocks = _parse_pdf_pages(pages)
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

    def rename_innermost(self, title: str) -> None:
        if self._entries:
            level, _ = self._entries[-1]
            self._entries[-1] = (level, title)

    @property
    def innermost(self) -> str:
        return self._entries[-1][1] if self._entries else ""

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


class _NormativeParser:
    """SPEC-012 (D3, D4): leis e regulamentos, linha a linha.

    TITULO, CAPITULO, Secao, Subsecao e Art. viram o caminho de secoes; o
    texto do caput, apos o rotulo do artigo, abre o primeiro bloco do artigo.
    Cada inciso, paragrafo ou alinea abre um bloco; as demais linhas continuam
    o bloco anterior (quebras de linha do PDF).
    """

    def __init__(self) -> None:
        self._sections = _SectionStack()
        self._builder = _BlockBuilder(self._sections)
        self._awaiting_subtitle = False

    def page(self, number: int | None) -> None:
        self._builder.flush()
        self._builder.page = number

    def boundary(self) -> None:
        """Fim de paragrafo (linha em branco ou paragrafo do DOCX)."""
        self._builder.flush()

    def line(self, raw_line: str) -> None:
        text = " ".join(raw_line.split())
        if not text:
            self.boundary()
            return
        heading = structural_heading(text)
        if heading is not None:
            self._enter(heading.level, heading.title, heading.remainder)
            return
        if self._awaiting_subtitle:
            self._awaiting_subtitle = False
            if _is_subtitle(text):
                self._sections.rename_innermost(
                    f"{self._sections.innermost} - {text}"
                )
                return
        if starts_legal_item(text):
            self._builder.start(BlockType.PARAGRAPH, text)
        else:
            self._builder.add(BlockType.PARAGRAPH, text)

    def table(self, text: str, header_lines: int) -> None:
        self._builder.flush()
        self._awaiting_subtitle = False
        self._builder.blocks.append(
            DocumentBlock(
                type=BlockType.TABLE,
                text=text,
                section_path=self._sections.path,
                page=self._builder.page,
                header_lines=header_lines,
            )
        )

    def finish(self) -> list[DocumentBlock]:
        self._builder.flush()
        return self._builder.blocks

    def _enter(self, level: int, title: str, remainder: str) -> None:
        self._builder.flush()
        self._sections.enter(level, title)
        # So o rotulo puro ("TITULO II") espera o nome na linha seguinte.
        self._awaiting_subtitle = level < ARTICLE_LEVEL and len(title.split()) == 2
        if remainder:
            self._builder.add(BlockType.PARAGRAPH, remainder)


def _is_subtitle(text: str) -> bool:
    if starts_legal_item(text) or text[-1] in _SENTENCE_END:
        return False
    if len(text.split()) > _SUBTITLE_MAX_WORDS:
        return False
    uppercase = text.upper() == text and any(char.isalpha() for char in text)
    return uppercase or _SUBTITLE_START.match(text) is not None


def _normative_pages(pages: list[str]) -> bool:
    return is_normative(line for page in pages for line in page.splitlines())


def _parse_normative_pages(pages: list[str]) -> list[DocumentBlock]:
    parser = _NormativeParser()
    for page_number, page_text in enumerate(pages, start=1):
        parser.page(page_number)
        for line in page_text.splitlines():
            parser.line(line)
    return parser.finish()


def _parse_normative_text(text: str) -> list[DocumentBlock]:
    parser = _NormativeParser()
    for line in text.splitlines():
        parser.line(line)
    return parser.finish()


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
        raise UnreadableDocumentError(
            f"could not read the PDF file: {exc}"
        ) from exc
    if ocr is None:
        return pages
    # Pagina digitalizada: so imagem, nenhum caractere na camada de texto.
    limit = getattr(ocr, "max_pages", None)
    scanned = sum(1 for text in pages if not text.strip())
    if limit is not None and scanned > limit:
        raise UnreadableDocumentError(
            f"the PDF has {scanned} pages without text; the OCR limit is {limit}."
        )
    return [
        text if text.strip() else ocr.recognize_page(raw_content, number)
        for number, text in enumerate(pages, start=1)
    ]


def _parse_docx(raw_content: bytes) -> list[DocumentBlock]:
    items = list(_iter_docx_items(raw_content))
    paragraphs = (text for kind, text, _ in items if kind is not BlockType.TABLE)
    if is_normative(paragraphs):
        return _parse_normative_docx(items)
    sections = _SectionStack()
    blocks: list[DocumentBlock] = []
    for kind, text, style_name in items:
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


def _parse_normative_docx(
    items: list[tuple[BlockType, str, str]],
) -> list[DocumentBlock]:
    """SPEC-012: no DOCX normativo, o texto decide a estrutura, nao o estilo."""
    parser = _NormativeParser()
    for kind, text, _ in items:
        if not text.strip():
            continue
        if kind is BlockType.TABLE:
            rows = text.count("\n") + 1
            parser.table(text, 1 if rows > 1 else 0)
            continue
        parser.line(text)
        parser.boundary()
    return parser.finish()


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
    return _text_blocks(_extract_plain_text(raw_content))


def _doc_blocks(raw_content: bytes) -> list[DocumentBlock]:
    return _text_blocks(_extract_doc_text(raw_content))


def _text_blocks(text: str) -> list[DocumentBlock]:
    if is_normative(text.splitlines()):
        return _parse_normative_text(text)
    return _parse_plain_text(text)


_BLOCK_EXTRACTORS: dict[str, Callable[[bytes], list[DocumentBlock]]] = {
    ".txt": _plain_blocks,
    ".md": _markdown_blocks,
    ".markdown": _markdown_blocks,
    ".docx": _parse_docx,
    ".doc": _doc_blocks,
}
