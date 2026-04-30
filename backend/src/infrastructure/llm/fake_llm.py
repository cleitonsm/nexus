from __future__ import annotations

from src.domain import LLMGateway


class FakeContextAwareLLM(LLMGateway):
    def generate(self, prompt: str, context_chunks: list[str]) -> str:
        if not context_chunks:
            return ""
        joined_context = " ".join(chunk.strip() for chunk in context_chunks if chunk.strip())
        if not joined_context:
            return ""
        return f"Com base no contexto: {joined_context}"
