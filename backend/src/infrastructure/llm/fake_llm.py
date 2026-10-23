from __future__ import annotations

from collections.abc import Iterator

from src.domain import (
    ChatMessage,
    ContextChunk,
    LLMCompletion,
    LLMGateway,
    LLMStreamChunk,
    TokenUsage,
)


class FakeContextAwareLLM(LLMGateway):
    """Responde com o contexto recebido e cita cada trecho pelo numero.

    O consumo e estimado por palavras, so para que testes de ponta a ponta
    vejam numeros diferentes de zero.
    """

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

    def generate_with_usage(
        self,
        *,
        prompt: str,
        context_chunks: list[ContextChunk],
        conversation_history: list[ChatMessage],
        system_instruction: str | None = None,
    ) -> LLMCompletion:
        text = self.generate(
            prompt=prompt,
            context_chunks=context_chunks,
            conversation_history=conversation_history,
        )
        sent = " ".join(
            [prompt, system_instruction or ""]
            + [chunk.text for chunk in context_chunks]
            + [item.content for item in conversation_history]
        )
        return LLMCompletion(
            text=text,
            usage=TokenUsage(
                input_tokens=len(sent.split()),
                output_tokens=len(text.split()),
            ),
        )

    def generate_stream(
        self,
        *,
        prompt: str,
        context_chunks: list[ContextChunk],
        conversation_history: list[ChatMessage],
        system_instruction: str | None = None,
    ) -> Iterator[LLMStreamChunk]:
        completion = self.generate_with_usage(
            prompt=prompt,
            context_chunks=context_chunks,
            conversation_history=conversation_history,
            system_instruction=system_instruction,
        )
        for word in completion.text.split(" "):
            yield LLMStreamChunk(text=f"{word} ")
        yield LLMStreamChunk(usage=completion.usage)
