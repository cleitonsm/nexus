from __future__ import annotations

from src.domain import ChatMessage, ContextChunk, LLMGateway


class FakeContextAwareLLM(LLMGateway):
    """Responde com o contexto recebido e cita cada trecho pelo numero."""

    def generate(
        self,
        *,
        prompt: str,
        context_chunks: list[ContextChunk],
        conversation_history: list[ChatMessage],
    ) -> str:
        if not context_chunks:
            return ""
        cited = " ".join(
            f"{chunk.text.strip()} [{chunk.number}]" for chunk in context_chunks
        )
        history_size = len(conversation_history)
        return f"Com base no contexto: {cited} (historico: {history_size} mensagens)"
