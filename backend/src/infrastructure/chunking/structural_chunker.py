from __future__ import annotations

from dataclasses import dataclass
from itertools import groupby

from src.domain import (
    BlockType,
    DocumentBlock,
    DocumentChunk,
    ExtractedDocument,
    TokenCounter,
)
from src.domain.chunking import SECTION_SEPARATOR

from .sentences import split_sentences

_BLOCK_BREAK = "\n\n"
_LINE_BREAK = "\n"
_SPACE = " "
_PROSE = (BlockType.PARAGRAPH, BlockType.LIST_ITEM)


@dataclass(frozen=True, slots=True)
class _Unit:
    """Trecho indivisivel de um chunk.

    ``separator`` e o que o liga ao trecho anterior; ``sentences`` guarda as
    frases de prosa usadas na sobreposicao (vazio para tabela e codigo).
    """

    text: str
    separator: str
    page: int | None
    sentences: tuple[str, ...] = ()


class StructuralDocumentChunker:
    """Fragmenta por secao, sem exceder o limite de tokens (SPEC-002)."""

    def __init__(
        self,
        *,
        token_counter: TokenCounter,
        max_tokens: int,
        overlap_sentences: int,
        max_prefix_tokens: int,
    ) -> None:
        if max_tokens < 1:
            raise ValueError("max_tokens must be positive.")
        if max_tokens > token_counter.max_tokens:
            raise ValueError(
                f"max_tokens ({max_tokens}) exceeds the embedding model "
                f"limit ({token_counter.max_tokens})."
            )
        if overlap_sentences < 0:
            raise ValueError("overlap_sentences must not be negative.")
        if not 0 <= max_prefix_tokens < max_tokens:
            raise ValueError(
                "max_prefix_tokens must be between 0 and max_tokens - 1."
            )
        self._counter = token_counter
        self._max_tokens = max_tokens
        self._overlap_sentences = overlap_sentences
        self._max_prefix_tokens = max_prefix_tokens

    def chunk(self, document: ExtractedDocument) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        sections = groupby(document.blocks, key=lambda block: block.section_path)
        for section_path, blocks in sections:
            prefix = self._prefix(section_path)
            units = self._units(list(blocks), prefix)
            for text, page in self._pack(units, prefix):
                chunks.append(
                    DocumentChunk(
                        index=len(chunks),
                        text=text,
                        section_path=section_path,
                        page=page,
                    )
                )
        return chunks

    # -- prefixo -----------------------------------------------------------

    def _prefix(self, section_path: tuple[str, ...]) -> str:
        """Caminho de titulos; descarta os mais externos se nao couber."""
        for start in range(len(section_path)):
            candidate = SECTION_SEPARATOR.join(section_path[start:])
            if self._counter.count(candidate) <= self._max_prefix_tokens:
                return candidate
        return ""

    # -- medida ------------------------------------------------------------

    def _fits(self, prefix: str, body: str) -> bool:
        return self._counter.count(_render(prefix, body)) <= self._max_tokens

    # -- unidades ----------------------------------------------------------

    def _units(self, blocks: list[DocumentBlock], prefix: str) -> list[_Unit]:
        units: list[_Unit] = []
        previous: DocumentBlock | None = None
        for block in blocks:
            separator = _block_separator(previous, block)
            units.extend(self._block_units(block, separator, prefix))
            previous = block
        return units

    def _block_units(
        self,
        block: DocumentBlock,
        separator: str,
        prefix: str,
    ) -> list[_Unit]:
        prose = block.type in _PROSE
        if self._fits(prefix, block.text):
            sentences = tuple(split_sentences(block.text)) if prose else ()
            return [_Unit(block.text, separator, block.page, sentences)]
        if prose:
            return self._prose_units(block, separator, prefix)
        return self._line_units(block, separator, prefix)

    def _prose_units(
        self,
        block: DocumentBlock,
        separator: str,
        prefix: str,
    ) -> list[_Unit]:
        units: list[_Unit] = []
        for sentence in split_sentences(block.text):
            if self._fits(prefix, sentence):
                pieces = [(sentence, (sentence,))]
            else:
                pieces = [(part, ()) for part in self._hard_split(sentence, prefix)]
            for text, sentences in pieces:
                joiner = separator if not units else _SPACE
                units.append(_Unit(text, joiner, block.page, sentences))
        return units

    def _line_units(
        self,
        block: DocumentBlock,
        separator: str,
        prefix: str,
    ) -> list[_Unit]:
        """Divide tabela ou codigo em linhas, repetindo o cabecalho."""
        header = block.header
        groups: list[str] = []
        current: list[str] = []
        for row in block.rows:
            candidate = _with_header(header, current + [row])
            if current and not self._fits(prefix, candidate):
                groups.append(_with_header(header, current))
                current = []
            if self._fits(prefix, _with_header(header, [row])):
                current.append(row)
            else:
                groups.extend(self._oversized_row(header, row, prefix))
        if current:
            groups.append(_with_header(header, current))
        return [
            _Unit(text, separator if index == 0 else _BLOCK_BREAK, block.page)
            for index, text in enumerate(groups)
        ]

    def _oversized_row(self, header: str, row: str, prefix: str) -> list[str]:
        """Linha que nao cabe nem sozinha com o cabecalho."""
        if self._fits(prefix, row):
            return [row]
        return self._hard_split(row, prefix)

    def _hard_split(self, text: str, prefix: str) -> list[str]:
        """Ultimo recurso: corta por palavras e, se preciso, por caracteres."""
        parts: list[str] = []
        current = ""
        for word in self._fitting_words(text, prefix):
            candidate = f"{current} {word}" if current else word
            if current and not self._fits(prefix, candidate):
                parts.append(current)
                candidate = word
            current = candidate
        if current:
            parts.append(current)
        return parts

    def _fitting_words(self, text: str, prefix: str) -> list[str]:
        words: list[str] = []
        pending = text.split()[::-1]
        while pending:
            word = pending.pop()
            if self._fits(prefix, word) or len(word) == 1:
                words.append(word)
                continue
            middle = len(word) // 2
            pending.extend([word[middle:], word[:middle]])
        return words

    # -- empacotamento -----------------------------------------------------

    def _pack(
        self,
        units: list[_Unit],
        prefix: str,
    ) -> list[tuple[str, int | None]]:
        packed: list[tuple[str, int | None]] = []
        current: list[_Unit] = []
        overlap = ""
        for unit in units:
            grown = _body(overlap, current + [unit])
            if current and not self._fits(prefix, grown):
                packed.append(_close(prefix, overlap, current))
                overlap = self._overlap(current)
                current = []
                if overlap and not self._fits(prefix, _body(overlap, [unit])):
                    overlap = ""
            current.append(unit)
        if current:
            packed.append(_close(prefix, overlap, current))
        return packed

    def _overlap(self, units: list[_Unit]) -> str:
        """Ultimas frases de prosa do chunk encerrado."""
        if self._overlap_sentences == 0:
            return ""
        trailing: list[str] = []
        covered = 0
        for unit in reversed(units):
            if not unit.sentences:
                break
            trailing = list(unit.sentences) + trailing
            covered += 1
            if len(trailing) >= self._overlap_sentences:
                break
        whole_chunk = covered == len(units) and (
            len(trailing) <= self._overlap_sentences
        )
        if not trailing or whole_chunk:
            return ""
        return _SPACE.join(trailing[-self._overlap_sentences :])


def _block_separator(previous: DocumentBlock | None, block: DocumentBlock) -> str:
    both_list_items = (
        previous is not None
        and previous.type is BlockType.LIST_ITEM
        and block.type is BlockType.LIST_ITEM
    )
    return _LINE_BREAK if both_list_items else _BLOCK_BREAK


def _with_header(header: str, rows: list[str]) -> str:
    lines = ([header] if header else []) + rows
    return _LINE_BREAK.join(lines)


def _body(overlap: str, units: list[_Unit]) -> str:
    parts: list[str] = [overlap] if overlap else []
    for unit in units:
        if parts:
            parts.append(unit.separator)
        parts.append(unit.text)
    return "".join(parts)


def _close(
    prefix: str,
    overlap: str,
    units: list[_Unit],
) -> tuple[str, int | None]:
    return _render(prefix, _body(overlap, units)), units[0].page


def _render(prefix: str, body: str) -> str:
    return f"{prefix}{_BLOCK_BREAK}{body}" if prefix else body
