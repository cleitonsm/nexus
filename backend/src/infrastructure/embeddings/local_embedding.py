from __future__ import annotations

import math
from hashlib import sha256


class LocalHashEmbeddingGateway:
    """
    Deterministic local embedding that does not depend on external services.
    """

    def __init__(self, *, vector_size: int = 384) -> None:
        if vector_size <= 0:
            raise ValueError("vector_size must be positive.")
        self._vector_size = vector_size

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_single(text) for text in texts]

    def _embed_single(self, text: str) -> list[float]:
        vector = [0.0] * self._vector_size
        for token in _tokenize(text):
            digest = sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], byteorder="big") % self._vector_size
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (digest[5] / 255.0)
            vector[bucket] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


def _tokenize(text: str) -> list[str]:
    return [token for token in text.lower().split() if token]
