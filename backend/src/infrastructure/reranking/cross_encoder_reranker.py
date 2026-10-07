from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from typing import Any

from src.domain import SearchResult


@lru_cache(maxsize=2)
def _load_model(model_name: str) -> tuple[Any, Any]:
    """Carrega o cross-encoder uma unica vez por processo.

    Usa o mesmo cache de arquivos dos embeddings (``HF_HOME``); com
    ``HF_HUB_OFFLINE=1`` o modelo precisa estar no cache.
    """
    try:
        from sentence_transformers import (  # type: ignore[import-not-found]
            CrossEncoder,
        )
        from torch import nn  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "sentence-transformers dependency is required for reranking."
        ) from exc
    return CrossEncoder(model_name, device="cpu"), nn.Sigmoid()


class CrossEncoderRerankerGateway:
    """Reranking local em CPU (RF-34, RNF-26, ADR 0007).

    A nota e a sigmoide da saida do modelo, entre 0 e 1, para que a nota
    minima (``RELEVANCE_MIN_SCORE``) tenha a mesma escala em qualquer modelo.
    """

    def __init__(self, *, model_name: str, batch_size: int = 16) -> None:
        if not model_name.strip():
            raise ValueError("reranker model name must not be empty.")
        self._model_name = model_name.strip()
        self._batch_size = batch_size
        self._model, self._activation = _load_model(self._model_name)

    @property
    def model_name(self) -> str:
        return self._model_name

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
    ) -> list[SearchResult]:
        if not candidates:
            return []
        scores = self._model.predict(
            [(query, candidate.text) for candidate in candidates],
            batch_size=self._batch_size,
            activation_fct=self._activation,
            show_progress_bar=False,
        )
        ranked = [
            replace(candidate, score=float(score))
            for candidate, score in zip(candidates, scores)
        ]
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked
