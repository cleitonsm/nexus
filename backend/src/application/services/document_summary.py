"""SPEC-018: chamadas ao LLM do resumo hierarquico (RN-62 a RN-66, D29, D33).

Os mini-resumos viram trechos numerados: o resumo final e o sob medida citam
``[n]`` apontando para eles, e a citacao guarda o titulo e a pagina inicial da
parte (D29). O texto do documento vai sempre como trecho, nunca nas instrucoes
de sistema (RN-31, RN-66).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain import (
    Citation,
    ContextChunk,
    Document,
    DocumentSummarySection,
    LLMGateway,
    TokenUsage,
    TransientServiceError,
    resolve_citations,
    strip_unknown_markers,
)

from .document_summary_prompts import TAILORED_INSTRUCTION, tailored_prompt


@dataclass(frozen=True, slots=True)
class SummaryCompletion:
    text: str
    citations: tuple[Citation, ...]
    usage: TokenUsage


def section_chunk_id(document: Document, position: int) -> str:
    return f"{document.id.value}:section:{position}"


def sections_as_context(
    document: Document, sections: list[DocumentSummarySection]
) -> list[ContextChunk]:
    """Mini-resumos numerados a partir de 1, na ordem do documento."""
    return [
        ContextChunk(
            number=number,
            text=section.content,
            document_id=document.id,
            chunk_id=section_chunk_id(document, section.position),
            source_name=document.source_name,
            section_path=section.title,
            page=section.page_start,
        )
        for number, section in enumerate(sections, start=1)
    ]


def complete_summary(
    llm: LLMGateway,
    context: list[ContextChunk],
    *,
    instruction: str,
    prompt: str,
) -> SummaryCompletion:
    """Uma chamada; marcadores que nao apontam para um trecho saem do texto."""
    completion = llm.generate_with_usage(
        prompt=prompt,
        context_chunks=context,
        conversation_history=[],
        system_instruction=instruction,
    )
    text = strip_unknown_markers(
        completion.text.strip(), {chunk.number for chunk in context}
    ).strip()
    if not text:
        # Resposta vazia do provedor: vale nova tentativa.
        raise TransientServiceError("the language model returned an empty summary.")
    return SummaryCompletion(
        text=text,
        citations=resolve_citations(text, context),
        usage=completion.usage,
    )


def tailored_summary(
    llm: LLMGateway,
    document: Document,
    sections: list[DocumentSummarySection],
    request: str,
) -> SummaryCompletion:
    """D33: resumo com recorte em uma chamada, sobre os mini-resumos gravados."""
    if not sections:
        raise ValueError("a tailored summary needs the stored mini summaries.")
    return complete_summary(
        llm,
        sections_as_context(document, sections),
        instruction=TAILORED_INSTRUCTION,
        prompt=tailored_prompt(request.strip()),
    )
