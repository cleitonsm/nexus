"""Adaptadores que envolvem chamadas externas em trechos (RF-56).

LLM, Qdrant e Keycloak ganham um trecho por chamada sem mudar os adaptadores
originais. So identificadores e contagens viram atributos (RNF-25).
"""

from __future__ import annotations

from collections.abc import Iterator

from src.domain import (
    AuthenticatedUser,
    ChatMessage,
    CollectionName,
    ContextChunk,
    LLMCompletion,
    LLMGateway,
    LLMStreamChunk,
    SearchResult,
    SparseVector,
    TokenVerifier,
    Tracer,
    VectorStoreGateway,
)


class TracedLLMGateway:
    def __init__(self, inner: LLMGateway, tracer: Tracer, *, model: str) -> None:
        self._inner = inner
        self._tracer = tracer
        self._model = model

    def _attributes(
        self,
        context_chunks: list[ContextChunk],
        history: list[ChatMessage],
        *,
        stream: bool,
    ) -> dict[str, str | int | bool]:
        return {
            "llm.model": self._model,
            "llm.stream": stream,
            "llm.context_chunks": len(context_chunks),
            "llm.history_messages": len(history),
        }

    def generate(
        self,
        *,
        prompt: str,
        context_chunks: list[ContextChunk],
        conversation_history: list[ChatMessage],
    ) -> str:
        return self.generate_with_usage(
            prompt=prompt,
            context_chunks=context_chunks,
            conversation_history=conversation_history,
        ).text

    def generate_with_usage(
        self,
        *,
        prompt: str,
        context_chunks: list[ContextChunk],
        conversation_history: list[ChatMessage],
        system_instruction: str | None = None,
    ) -> LLMCompletion:
        with self._tracer.span(
            "llm.chat_completion",
            self._attributes(context_chunks, conversation_history, stream=False),
        ) as span:
            completion = self._inner.generate_with_usage(
                prompt=prompt,
                context_chunks=context_chunks,
                conversation_history=conversation_history,
                system_instruction=system_instruction,
            )
            span.set_attribute("llm.input_tokens", completion.usage.input_tokens)
            span.set_attribute("llm.output_tokens", completion.usage.output_tokens)
            return completion

    def generate_stream(
        self,
        *,
        prompt: str,
        context_chunks: list[ContextChunk],
        conversation_history: list[ChatMessage],
        system_instruction: str | None = None,
    ) -> Iterator[LLMStreamChunk]:
        with self._tracer.span(
            "llm.chat_completion",
            self._attributes(context_chunks, conversation_history, stream=True),
        ) as span:
            parts = 0
            for chunk in self._inner.generate_stream(
                prompt=prompt,
                context_chunks=context_chunks,
                conversation_history=conversation_history,
                system_instruction=system_instruction,
            ):
                if chunk.usage is not None:
                    span.set_attribute("llm.input_tokens", chunk.usage.input_tokens)
                    span.set_attribute("llm.output_tokens", chunk.usage.output_tokens)
                if chunk.text:
                    parts += 1
                yield chunk
            span.set_attribute("llm.stream_parts", parts)


class TracedVectorStore:
    """Trecho na busca; as demais operacoes passam direto ao adaptador."""

    def __init__(self, inner: VectorStoreGateway, tracer: Tracer) -> None:
        self._inner = inner
        self._tracer = tracer

    def hybrid_search(
        self,
        collection_name: CollectionName,
        dense_vector: list[float],
        sparse_vector: SparseVector,
        limit: int,
        payload_filter: dict[str, str] | None = None,
        *,
        user_groups: frozenset[str] | None,
    ) -> list[SearchResult]:
        with self._tracer.span(
            "qdrant.hybrid_search",
            {"db.system": "qdrant", "qdrant.limit": limit},
        ) as span:
            results = self._inner.hybrid_search(
                collection_name,
                dense_vector,
                sparse_vector,
                limit,
                payload_filter,
                user_groups=user_groups,
            )
            span.set_attribute("qdrant.results", len(results))
            return results

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


class TracedTokenVerifier:
    def __init__(self, inner: TokenVerifier, tracer: Tracer) -> None:
        self._inner = inner
        self._tracer = tracer

    def verify(self, token: str) -> AuthenticatedUser:
        with self._tracer.span("keycloak.verify_access", {"auth.provider": "keycloak"}):
            return self._inner.verify(token)
