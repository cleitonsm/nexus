"""Dubles compartilhados pelos testes de recuperacao e de chat (SPEC-003)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

from src.application.services import ContextRetriever, RetrievalSettings
from src.domain import (
    ChatMessage,
    CollectionName,
    ContextChunk,
    DocumentId,
    LLMCompletion,
    LLMStreamChunk,
    SearchResult,
    SparseVector,
    TokenUsage,
)
from src.infrastructure.embeddings import Bm25SparseEmbeddingGateway


class WordTokenCounter:
    """Um token por palavra: torna os orcamentos previsiveis nos testes."""

    max_tokens = 128

    def count(self, text: str) -> int:
        return len(text.split())


class SingleVectorEmbeddingGateway:
    model_name = "fake"
    dimension = 1

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0]


class ScriptedVectorStore:
    """Devolve, a cada busca, a proxima lista de candidatos roteirizada."""

    def __init__(self, results: list[list[SearchResult]]) -> None:
        self._results = list(results)
        self.calls: list[dict[str, object]] = []

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
        self.calls.append(
            {
                "collection": collection_name.value,
                "dense_vector": dense_vector,
                "sparse_vector": sparse_vector,
                "limit": limit,
                "payload_filter": payload_filter,
                "user_groups": user_groups,
            }
        )
        if not self._results:
            return []
        return self._results.pop(0)[:limit]


class ScriptedReranker:
    """Nota por texto; sem roteiro, mantem a nota recebida da busca."""

    model_name = "fake-reranker"

    def __init__(self, scores: dict[str, float] | None = None) -> None:
        self._scores = scores or {}
        self.calls: list[tuple[str, list[SearchResult]]] = []

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
    ) -> list[SearchResult]:
        self.calls.append((query, list(candidates)))
        ranked = [
            replace(item, score=self._scores.get(item.text, item.score))
            for item in candidates
        ]
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked


class ScriptedLLM:
    """Devolve as respostas na ordem roteirizada e registra as chamadas.

    ``usage`` e o consumo informado a cada chamada; no streaming, a resposta
    sai em partes de ``chunk_size`` caracteres e o consumo vem no fim.
    """

    def __init__(
        self,
        *answers: str,
        usage: TokenUsage | None = None,
        chunk_size: int = 4,
    ) -> None:
        self._answers = list(answers)
        self.calls: list[dict[str, object]] = []
        self.usage = usage or TokenUsage()
        self.chunk_size = chunk_size
        self.system_instructions: list[str | None] = []

    def generate_with_usage(
        self,
        *,
        prompt: str,
        context_chunks: list[ContextChunk],
        conversation_history: list[ChatMessage],
        system_instruction: str | None = None,
    ) -> LLMCompletion:
        self.system_instructions.append(system_instruction)
        text = self.generate(
            prompt=prompt,
            context_chunks=context_chunks,
            conversation_history=conversation_history,
        )
        if self.calls:
            self.calls[-1]["system_instruction"] = system_instruction
        return LLMCompletion(text=text, usage=self.usage)

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
        text = completion.text
        for start in range(0, len(text), self.chunk_size):
            yield LLMStreamChunk(text=text[start : start + self.chunk_size])
        yield LLMStreamChunk(usage=completion.usage)

    def generate(
        self,
        *,
        prompt: str,
        context_chunks: list[ContextChunk],
        conversation_history: list[ChatMessage],
    ) -> str:
        self.calls.append(
            {
                "prompt": prompt,
                "context_chunks": list(context_chunks),
                "conversation_history": list(conversation_history),
            }
        )
        if len(self._answers) > 1:
            return self._answers.pop(0)
        return self._answers[0] if self._answers else ""


def hit(
    document_id: str,
    text: str = "trecho",
    *,
    score: float = 0.9,
    index: int = 0,
    source_name: str = "",
    section_path: str = "",
    page: int | None = None,
) -> SearchResult:
    return SearchResult(
        chunk_id=f"{document_id}:{index}",
        document_id=DocumentId(document_id),
        score=score,
        text=text,
        source_name=source_name,
        section_path=section_path,
        page=page,
    )


def build_retriever(
    vector_store: ScriptedVectorStore,
    *,
    reranker: ScriptedReranker | None = None,
    settings: RetrievalSettings | None = None,
) -> ContextRetriever:
    return ContextRetriever(
        embedding_gateway=SingleVectorEmbeddingGateway(),
        sparse_embedding_gateway=Bm25SparseEmbeddingGateway(),
        vector_store_gateway=vector_store,
        reranker_gateway=reranker or ScriptedReranker(),
        settings=settings or RetrievalSettings(),
    )
