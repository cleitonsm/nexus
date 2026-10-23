from __future__ import annotations

from functools import lru_cache
from typing import Any


@lru_cache(maxsize=2)
def _load_model(model_name: str) -> Any:
    """Carrega o modelo uma unica vez por processo (SPEC-002).

    O cache de arquivos fica no diretorio indicado por ``HF_HOME`` (volume
    ``backend_cache``). Com ``HF_HUB_OFFLINE=1`` nenhuma chamada de rede e
    feita e o modelo precisa estar no cache.
    """
    try:
        from sentence_transformers import (  # type: ignore[import-not-found]
            SentenceTransformer,
        )
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "sentence-transformers dependency is required for embeddings."
        ) from exc
    return SentenceTransformer(model_name, device="cpu")


class SentenceTransformerEmbeddingGateway:
    """Embeddings semanticos locais (ADR 0004 e ADR 0006)."""

    def __init__(self, *, model_name: str, expected_dimension: int) -> None:
        if not model_name.strip():
            raise ValueError("embedding model name must not be empty.")
        self._model_name = model_name.strip()
        self._model = _load_model(self._model_name)
        actual = int(self._model.get_sentence_embedding_dimension())
        if actual != expected_dimension:
            raise ValueError(
                f"embedding model '{self._model_name}' has dimension {actual}, "
                f"but EMBEDDING_VECTOR_SIZE is {expected_dimension}."
            )
        self._dimension = actual

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text])[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [[float(value) for value in vector] for vector in vectors]


class SentenceTransformerTokenCounter:
    """Mede textos com o tokenizador do proprio modelo de embedding."""

    def __init__(self, *, model_name: str) -> None:
        self._model = _load_model(model_name.strip())

    @property
    def max_tokens(self) -> int:
        return int(self._model.max_seq_length)

    def count(self, text: str) -> int:
        encoded = self._model.tokenizer(
            text,
            add_special_tokens=True,
            truncation=False,
            return_attention_mask=False,
            return_token_type_ids=False,
        )
        return len(encoded["input_ids"])
