from __future__ import annotations

from dataclasses import dataclass

from src.domain import (
    AssistantId,
    CollectionName,
    EmbeddingGateway,
    RerankerGateway,
    SearchResult,
    SparseEmbeddingGateway,
    VectorStoreGateway,
)


@dataclass(frozen=True, slots=True)
class RetrievalSettings:
    """Parametros da SPEC-003; os valores iniciais serao calibrados no CT-22."""

    candidates: int = 30
    top_n: int = 5
    min_score: float = 0.5
    context_token_budget: int = 2000
    history_token_budget: int = 1500

    def __post_init__(self) -> None:
        if self.candidates < 1 or self.top_n < 1:
            raise ValueError("candidates and top_n must be positive.")
        if not 0.0 <= self.min_score <= 1.0:
            raise ValueError("min_score must be between 0 and 1.")
        if self.context_token_budget < 1:
            raise ValueError("context_token_budget must be positive.")
        if self.history_token_budget < 0:
            raise ValueError("history_token_budget must not be negative.")


class ContextRetriever:
    """Busca hibrida, reranking e nota minima; usado pelo chat e pela avaliacao."""

    def __init__(
        self,
        *,
        embedding_gateway: EmbeddingGateway,
        sparse_embedding_gateway: SparseEmbeddingGateway,
        vector_store_gateway: VectorStoreGateway,
        reranker_gateway: RerankerGateway,
        settings: RetrievalSettings,
    ) -> None:
        self._embedding_gateway = embedding_gateway
        self._sparse_embedding_gateway = sparse_embedding_gateway
        self._vector_store_gateway = vector_store_gateway
        self._reranker_gateway = reranker_gateway
        self._settings = settings

    @property
    def settings(self) -> RetrievalSettings:
        return self._settings

    def search(
        self,
        assistant_id: AssistantId,
        query: str,
        payload_filter: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        """Candidatos da busca hibrida, restritos a collection do assistente."""
        dense_vector = self._embedding_gateway.embed_query(query)
        if not dense_vector:
            return []
        results = self._vector_store_gateway.hybrid_search(
            collection_name=CollectionName.from_assistant_id(assistant_id),
            dense_vector=dense_vector,
            sparse_vector=self._sparse_embedding_gateway.embed_query(query),
            limit=self._settings.candidates,
            payload_filter=payload_filter,
        )
        return [item for item in results if item.text.strip()]

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        limit: int | None = None,
    ) -> list[SearchResult]:
        """Os ``limit`` melhores candidatos (padrao ``top_n``), ja com a nota."""
        if not candidates:
            return []
        ranked = sorted(
            self._reranker_gateway.rerank(query, candidates),
            key=lambda item: item.score,
            reverse=True,
        )
        return ranked[: max(limit or self._settings.top_n, 1)]

    def select_relevant(self, ranked: list[SearchResult]) -> list[SearchResult]:
        """RN-17: so trechos com nota igual ou superior a minima viram contexto."""
        return [
            item
            for item in ranked[: self._settings.top_n]
            if item.score >= self._settings.min_score
        ]
