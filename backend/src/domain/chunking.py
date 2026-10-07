from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .errors import DomainValidationError

SECTION_SEPARATOR = " > "


class BlockType(StrEnum):
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    CODE = "code"


def _validate_section_path(section_path: tuple[str, ...]) -> tuple[str, ...]:
    cleaned = tuple(title.strip() for title in section_path)
    if any(not title for title in cleaned):
        raise DomainValidationError("section_path titles must not be empty.")
    return cleaned


def _validate_page(page: int | None) -> None:
    if page is not None and page < 1:
        raise DomainValidationError("page must be greater than or equal to 1.")


@dataclass(frozen=True, slots=True)
class DocumentBlock:
    """Unidade estrutural extraida de um documento.

    Em tabelas, ``header_lines`` informa quantas linhas iniciais formam o
    cabecalho, que deve acompanhar as demais linhas em qualquer divisao.
    """

    type: BlockType
    text: str
    section_path: tuple[str, ...] = ()
    page: int | None = None
    header_lines: int = 0

    def __post_init__(self) -> None:
        text = self.text.strip()
        if not text:
            raise DomainValidationError("document block text must not be empty.")
        object.__setattr__(self, "text", text)
        object.__setattr__(
            self, "section_path", _validate_section_path(self.section_path)
        )
        _validate_page(self.page)
        self._validate_header_lines()

    def _validate_header_lines(self) -> None:
        if self.header_lines < 0:
            raise DomainValidationError("header_lines must not be negative.")
        if self.header_lines == 0:
            return
        if self.type is not BlockType.TABLE:
            raise DomainValidationError("header_lines applies only to tables.")
        if self.header_lines >= len(self.text.split("\n")):
            raise DomainValidationError(
                "header_lines must leave at least one table row."
            )

    @property
    def header(self) -> str:
        return "\n".join(self.text.split("\n")[: self.header_lines])

    @property
    def rows(self) -> tuple[str, ...]:
        return tuple(self.text.split("\n")[self.header_lines :])


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    blocks: tuple[DocumentBlock, ...]

    def __post_init__(self) -> None:
        if not self.blocks:
            raise DomainValidationError(
                "extracted document must contain at least one block."
            )

    @property
    def plain_text(self) -> str:
        return "\n\n".join(block.text for block in self.blocks)


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    index: int
    text: str
    section_path: tuple[str, ...] = ()
    page: int | None = None

    def __post_init__(self) -> None:
        if self.index < 0:
            raise DomainValidationError("chunk index must not be negative.")
        if not self.text.strip():
            raise DomainValidationError("chunk text must not be empty.")
        object.__setattr__(
            self, "section_path", _validate_section_path(self.section_path)
        )
        _validate_page(self.page)

    @property
    def section_label(self) -> str:
        return SECTION_SEPARATOR.join(self.section_path)
