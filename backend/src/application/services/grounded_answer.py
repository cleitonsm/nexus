from __future__ import annotations

import logging
from dataclasses import dataclass

from src.domain import (
    ChatMessage,
    Citation,
    ContextChunk,
    LLMGateway,
    SearchResult,
    TokenCounter,
    resolve_citations,
    strip_unknown_markers,
)

logger = logging.getLogger(__name__)

DEFAULT_ANSWER_INSTRUCTION = (
    "Responda de forma objetiva usando apenas o contexto recuperado."
)

CITATION_INSTRUCTION = (
    "Cada trecho do contexto tem um numero. Ao final de cada afirmacao, "
    "indique o trecho que a sustenta com o marcador [n], por exemplo [1] ou "
    "[1][3]. Use somente os numeros dos trechos fornecidos e nao afirme nada "
    "que nao esteja neles."
)

REWRITE_INSTRUCTION = (
    "Reescreva a pergunta abaixo como uma pergunta independente, que possa "
    "ser entendida sem a conversa anterior, explicitando o assunto quando "
    "ele estiver implicito. Nao responda a pergunta. Devolva somente a "
    "pergunta reescrita, em uma unica linha."
)


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    """Resposta aceita: texto com ao menos uma citacao valida (RN-18)."""

    text: str
    citations: tuple[Citation, ...]


def trim_history(
    history: list[ChatMessage],
    token_counter: TokenCounter,
    budget: int,
) -> list[ChatMessage]:
    """RN-19: mensagens mais recentes, contiguas, que cabem no orcamento."""
    kept: list[ChatMessage] = []
    used = 0
    for message in reversed(history):
        used += token_counter.count(message.content)
        if used > budget:
            break
        kept.append(message)
    kept.reverse()
    return kept


def fit_context(
    results: list[SearchResult],
    token_counter: TokenCounter,
    budget: int,
) -> list[ContextChunk]:
    """Numera os trechos, na ordem de relevancia, ate esgotar o orcamento."""
    chunks: list[ContextChunk] = []
    used = 0
    for result in results:
        used += token_counter.count(result.text)
        if used > budget:
            break
        chunks.append(
            ContextChunk(
                number=len(chunks) + 1,
                text=result.text,
                document_id=result.document_id,
                chunk_id=result.chunk_id,
                source_name=result.source_name,
                section_path=result.section_path,
                page=result.page,
                score=result.score,
            )
        )
    return chunks


class GroundedAnswerGenerator:
    """Reescreve a pergunta e gera respostas com citacoes validadas."""

    def __init__(self, *, llm_gateway: LLMGateway) -> None:
        self._llm_gateway = llm_gateway

    def rewrite_question(
        self,
        question: str,
        history: list[ChatMessage],
    ) -> str:
        """RF-36: sem historico a pergunta segue como foi digitada.

        A reescrita e uma melhoria da busca: se o LLM falhar, a pergunta
        original e usada e a falha fica registrada no log.
        """
        if not history:
            return question
        try:
            rewritten = self._llm_gateway.generate(
                prompt=f"{REWRITE_INSTRUCTION}\nPergunta: {question}",
                context_chunks=[],
                conversation_history=history,
            )
        except (ValueError, RuntimeError) as exc:
            logger.warning(
                "chat.rewrite.failed",
                extra={"error_type": type(exc).__name__},
            )
            return question
        return " ".join(rewritten.split()) or question

    def generate(
        self,
        *,
        question: str,
        context_chunks: list[ContextChunk],
        history: list[ChatMessage],
        instruction: str | None = None,
    ) -> str:
        if not context_chunks:
            return ""
        return self._llm_gateway.generate(
            prompt=build_answer_prompt(question, instruction),
            context_chunks=context_chunks,
            conversation_history=history,
        ).strip()

    def validate(
        self,
        text: str,
        context_chunks: list[ContextChunk],
    ) -> GroundedAnswer | None:
        """RN-18: None quando a resposta deve ser trocada pelo fallback.

        Marcadores que nao apontam para nenhum trecho saem do texto aceito.
        """
        citations = resolve_citations(text, context_chunks)
        if not text.strip() or not citations:
            return None
        cleaned = strip_unknown_markers(
            text.strip(),
            {citation.number for citation in citations},
        )
        return GroundedAnswer(text=cleaned, citations=citations)

    def answer(
        self,
        *,
        question: str,
        context_chunks: list[ContextChunk],
        history: list[ChatMessage],
        instruction: str | None = None,
    ) -> GroundedAnswer | None:
        """Gera e valida; usado onde nao ha grafo (avaliacao)."""
        text = self.generate(
            question=question,
            context_chunks=context_chunks,
            history=history,
            instruction=instruction,
        )
        return self.validate(text, context_chunks)


def build_answer_prompt(question: str, instruction: str | None) -> str:
    base = (instruction or "").strip() or DEFAULT_ANSWER_INSTRUCTION
    return f"{base}\n{CITATION_INSTRUCTION}\nPergunta: {question}"
