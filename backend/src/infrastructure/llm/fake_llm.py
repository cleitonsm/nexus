from __future__ import annotations

from src.domain import ChatMessage, LLMGateway


class FakeContextAwareLLM(LLMGateway):
    def generate(
        self,
        *,
        prompt: str,
        context_chunks: list[str],
        conversation_history: list[ChatMessage],
    ) -> str:
        if not context_chunks:
            return ""
        joined_context = " ".join(chunk.strip() for chunk in context_chunks if chunk.strip())
        if not joined_context:
            return ""
        history_size = len(conversation_history)
        return f"Com base no contexto: {joined_context} (historico: {history_size} mensagens)"
