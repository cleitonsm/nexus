from __future__ import annotations

from src.domain import ContextChunk, LLMGateway

# A rubrica e versionada com o codigo: altera-la muda o significado da metrica
# de fidelidade e exige registrar nova linha de base.
JUDGE_RUBRIC = (
    "Voce e um avaliador rigoroso. Verifique se TODAS as afirmacoes da "
    "resposta abaixo sao sustentadas pelo contexto recuperado. "
    "Responda apenas SIM ou NAO, sem explicacoes."
)


class LLMAnswerJudge:
    """Julga a fidelidade de uma resposta usando o LLM ja configurado."""

    def __init__(self, *, llm_gateway: LLMGateway) -> None:
        self._llm_gateway = llm_gateway

    def is_faithful(
        self,
        *,
        question: str,
        answer: str,
        context_chunks: list[str],
    ) -> bool:
        texts = [chunk for chunk in context_chunks if chunk.strip()]
        if not texts:
            return False
        verdict = self._llm_gateway.generate(
            prompt=(
                f"{JUDGE_RUBRIC}\n"
                f"Pergunta: {question}\n"
                f"Resposta a avaliar: {answer}"
            ),
            context_chunks=[
                ContextChunk(number=number, text=text)
                for number, text in enumerate(texts, start=1)
            ],
            conversation_history=[],
        )
        return verdict.strip().upper().startswith("SIM")
