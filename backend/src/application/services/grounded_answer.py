from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass

from src.domain import (
    ChatMessage,
    Citation,
    ContextChunk,
    LegalReference,
    LLMCompletion,
    LLMGateway,
    LLMStreamChunk,
    SearchResult,
    TokenCounter,
    describe_items,
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

# SPEC-012 (D1, D2): vale para todos os assistentes, depois do prompt inicial.
# Validacao de 2026-10-27: com "resumo explicativo" solto, o LLM acrescentava
# finalidades e consequencias fora dos trechos (fidelidade 0,5 no conjunto
# normativo). O resumo so pode sintetizar o que os trechos dizem (RN-18).
# Na mesma validacao, o resumo do Art. 7º trocou "quadro social" da associacao
# por "clube" (termo de outro documento): os termos do texto ficam mantidos.
FORMAT_INSTRUCTION = (
    "Seja sucinto: responda primeiro ao que foi perguntado, em poucos "
    "paragrafos, sem repetir o texto dos trechos. Quando o conteudo pedido for "
    "enumerado (incisos, alineas, itens, requisitos, etapas), liste todos os "
    "itens na ordem original, um por linha, com o identificador do item (por "
    "exemplo \"I -\", \"a)\", \"§ 1º\") e uma frase curta que resuma o "
    "proprio texto do item, cada um com sua citacao. Depois da lista, escreva "
    "um resumo explicativo de ate cinco frases que apenas agrupe e sintetize o "
    "que os trechos dizem, tambem com citacoes. Nunca acrescente finalidades, "
    "exemplos, consequencias, interpretacoes ou conhecimento que nao estejam "
    "nos trechos, nem no resumo. Nos itens e no resumo, use os termos do "
    "proprio texto: nao troque termos tecnicos por sinonimos nem use palavras "
    "de outro documento."
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


def fit_structural_context(
    results: list[SearchResult],
    reference: LegalReference,
    token_counter: TokenCounter,
    budget: int,
) -> tuple[list[ContextChunk], str | None]:
    """D8 e RN-36: o dispositivo ate o orcamento e o aviso do que ficou de fora."""
    chunks = fit_context(results, token_counter, budget)
    omitted = results[len(chunks):]
    if not omitted:
        return chunks, None
    items = describe_items(item.text for item in omitted) or "os trechos finais"
    notice = (
        f"Aviso: o contexto nao inclui todo o Art. {reference.article}; ficaram "
        f"de fora {items}. Diga isso ao usuario na resposta."
    )
    return chunks, notice


class GroundedAnswerGenerator:
    """Reescreve a pergunta e gera respostas com citacoes validadas."""

    def __init__(self, *, llm_gateway: LLMGateway) -> None:
        self._llm_gateway = llm_gateway

    def rewrite_question(
        self,
        question: str,
        history: list[ChatMessage],
    ) -> str:
        return self.rewrite(question, history).text

    def rewrite(
        self,
        question: str,
        history: list[ChatMessage],
    ) -> LLMCompletion:
        """RF-36: sem historico a pergunta segue como foi digitada.

        A reescrita e uma melhoria da busca: se o LLM falhar, a pergunta
        original e usada e a falha fica registrada no log.
        """
        if not history:
            return LLMCompletion(text=question)
        try:
            completion = self._llm_gateway.generate_with_usage(
                prompt=f"{REWRITE_INSTRUCTION}\nPergunta: {question}",
                context_chunks=[],
                conversation_history=history,
            )
        except (ValueError, RuntimeError) as exc:
            logger.warning(
                "chat.rewrite.failed",
                extra={"error_type": type(exc).__name__},
            )
            return LLMCompletion(text=question)
        return LLMCompletion(
            text=" ".join(completion.text.split()) or question,
            usage=completion.usage,
        )

    def generate(
        self,
        *,
        question: str,
        context_chunks: list[ContextChunk],
        history: list[ChatMessage],
        instruction: str | None = None,
        notice: str | None = None,
    ) -> str:
        return self.generate_completion(
            question=question,
            context_chunks=context_chunks,
            history=history,
            instruction=instruction,
            notice=notice,
        ).text

    def generate_completion(
        self,
        *,
        question: str,
        context_chunks: list[ContextChunk],
        history: list[ChatMessage],
        instruction: str | None = None,
        notice: str | None = None,
    ) -> LLMCompletion:
        """RN-31: instrucoes no sistema; trechos e pergunta, fora dele."""
        if not context_chunks:
            return LLMCompletion(text="")
        completion = self._llm_gateway.generate_with_usage(
            prompt=build_answer_prompt(question),
            context_chunks=context_chunks,
            conversation_history=history,
            system_instruction=build_answer_instruction(instruction, notice),
        )
        return LLMCompletion(text=completion.text.strip(), usage=completion.usage)

    def generate_stream(
        self,
        *,
        question: str,
        context_chunks: list[ContextChunk],
        history: list[ChatMessage],
        instruction: str | None = None,
        notice: str | None = None,
    ) -> Iterator[LLMStreamChunk]:
        """RF-58: mesma chamada da geracao completa, entregue em partes."""
        if not context_chunks:
            return iter(())
        return self._llm_gateway.generate_stream(
            prompt=build_answer_prompt(question),
            context_chunks=context_chunks,
            conversation_history=history,
            system_instruction=build_answer_instruction(instruction, notice),
        )

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
        notice: str | None = None,
    ) -> GroundedAnswer | None:
        """Gera e valida; usado onde nao ha grafo (avaliacao)."""
        text = self.generate(
            question=question,
            context_chunks=context_chunks,
            history=history,
            instruction=instruction,
            notice=notice,
        )
        return self.validate(text, context_chunks)


def build_answer_instruction(
    instruction: str | None,
    notice: str | None = None,
) -> str:
    """Prompt inicial, regra de formato e regra de citacao vao no sistema.

    ``notice`` e o aviso de conteudo omitido pelo orcamento (RN-36).
    """
    base = (instruction or "").strip() or DEFAULT_ANSWER_INSTRUCTION
    parts = [base, FORMAT_INSTRUCTION, CITATION_INSTRUCTION]
    if notice:
        parts.append(notice.strip())
    return "\n".join(parts)


def build_answer_prompt(question: str) -> str:
    return f"Pergunta: {question}"
