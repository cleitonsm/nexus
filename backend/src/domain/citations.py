from __future__ import annotations

from dataclasses import dataclass
from re import Match
from re import compile as compile_pattern

from .errors import DomainValidationError
from .value_objects import DocumentId

# Aceita [1], [1][2] e [1, 2].
_MARKER = compile_pattern(r"\[(\d+(?:\s*,\s*\d+)*)\]")
_MARKER_WITH_SPACE = compile_pattern(r"([ \t]*)\[(\d+(?:\s*,\s*\d+)*)\]")


@dataclass(frozen=True, slots=True)
class ContextChunk:
    """Trecho numerado enviado ao LLM; o numero e o alvo do marcador ``[n]``."""

    number: int
    text: str
    document_id: DocumentId | None = None
    chunk_id: str = ""
    source_name: str = ""
    section_path: str = ""
    page: int | None = None
    score: float = 0.0

    def __post_init__(self) -> None:
        if self.number < 1:
            raise DomainValidationError(
                "context chunk number must be greater than or equal to 1."
            )
        if not self.text.strip():
            raise DomainValidationError("context chunk text must not be empty.")


@dataclass(frozen=True, slots=True)
class Citation:
    """Fonte de uma resposta: o trecho recuperado que um marcador referencia."""

    number: int
    document_id: DocumentId
    chunk_id: str
    source_name: str
    excerpt: str
    section_path: str = ""
    page: int | None = None
    score: float = 0.0

    def __post_init__(self) -> None:
        if self.number < 1:
            raise DomainValidationError(
                "citation number must be greater than or equal to 1."
            )
        if not self.chunk_id.strip():
            raise DomainValidationError("citation chunk_id must not be empty.")
        if not self.excerpt.strip():
            raise DomainValidationError("citation excerpt must not be empty.")
        if self.page is not None and self.page < 1:
            raise DomainValidationError(
                "citation page must be greater than or equal to 1."
            )


def cited_numbers(answer: str) -> tuple[int, ...]:
    """Numeros citados na resposta, sem repeticao, na ordem em que aparecem."""
    numbers: list[int] = []
    for match in _MARKER.finditer(answer):
        for raw in match.group(1).split(","):
            number = int(raw)
            if number not in numbers:
                numbers.append(number)
    return tuple(numbers)


def strip_unknown_markers(answer: str, valid_numbers: set[int]) -> str:
    """Remove do texto os marcadores que nao apontam para nenhum trecho.

    Em um marcador com varios numeros, ficam apenas os validos. Um marcador
    removido leva junto o espaco que o antecede.
    """

    def _replace(match: Match[str]) -> str:
        kept = [
            raw.strip()
            for raw in match.group(2).split(",")
            if int(raw) in valid_numbers
        ]
        if not kept:
            return ""
        return f"{match.group(1)}[{', '.join(kept)}]"

    return _MARKER_WITH_SPACE.sub(_replace, answer)


def resolve_citations(
    answer: str,
    context_chunks: list[ContextChunk],
) -> tuple[Citation, ...]:
    """Citacoes validas: marcadores que apontam para trechos enviados (RN-18).

    Marcadores que nao correspondem a nenhum trecho nao geram citacao; a
    resposta so e aceita por quem chama se ao menos uma citacao valida restar.
    """
    by_number = {chunk.number: chunk for chunk in context_chunks}
    citations: list[Citation] = []
    for number in cited_numbers(answer):
        chunk = by_number.get(number)
        if chunk is None or chunk.document_id is None:
            continue
        citations.append(_to_citation(chunk, chunk.document_id))
    return tuple(citations)


def _to_citation(chunk: ContextChunk, document_id: DocumentId) -> Citation:
    return Citation(
        number=chunk.number,
        document_id=document_id,
        chunk_id=chunk.chunk_id,
        source_name=chunk.source_name,
        excerpt=chunk.text,
        section_path=chunk.section_path,
        page=chunk.page,
        score=chunk.score,
    )
