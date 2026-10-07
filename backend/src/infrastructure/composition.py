"""Montagem dos adaptadores de indexacao e de recuperacao.

Usada pelos pontos de entrada (API e comando de avaliacao), para que ambos
indexem e recuperem com exatamente o mesmo pipeline e os mesmos parametros.
"""

from __future__ import annotations

import os
from functools import lru_cache

from src.application.services import DocumentIndexer, RetrievalSettings
from src.infrastructure.chunking import StructuralDocumentChunker
from src.infrastructure.documents import SupportedDocumentExtractor
from src.infrastructure.embeddings import (
    DEFAULT_BM25_AVERAGE_LENGTH,
    DEFAULT_BM25_B,
    DEFAULT_BM25_K1,
    Bm25SparseEmbeddingGateway,
    SentenceTransformerEmbeddingGateway,
    SentenceTransformerTokenCounter,
)
from src.infrastructure.reranking import CrossEncoderRerankerGateway
from src.infrastructure.storage import LocalDocumentFileStorage

DEFAULT_EMBEDDING_MODEL = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
DEFAULT_VECTOR_SIZE = 384
DEFAULT_OVERLAP_SENTENCES = 1
DEFAULT_PREFIX_MAX_TOKENS = 32
DEFAULT_MAX_FILE_BYTES = 20 * 1024 * 1024
DEFAULT_DOCUMENTS_DIR = "/app/data/documents"
DEFAULT_RERANKER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


def embedding_model_name() -> str:
    return os.getenv("EMBEDDING_MODEL_NAME", "").strip() or DEFAULT_EMBEDDING_MODEL


@lru_cache(maxsize=1)
def build_embedding_gateway() -> SentenceTransformerEmbeddingGateway:
    return SentenceTransformerEmbeddingGateway(
        model_name=embedding_model_name(),
        expected_dimension=_int_env("EMBEDDING_VECTOR_SIZE", DEFAULT_VECTOR_SIZE),
    )


@lru_cache(maxsize=1)
def build_token_counter() -> SentenceTransformerTokenCounter:
    """Tokenizador do modelo de embedding.

    Mede os chunks e, por aproximacao, os orcamentos de contexto e de
    historico: o tokenizador do provedor de LLM nao esta disponivel localmente.
    """
    return SentenceTransformerTokenCounter(model_name=embedding_model_name())


@lru_cache(maxsize=1)
def build_sparse_embedding_gateway() -> Bm25SparseEmbeddingGateway:
    """Mudar estes parametros exige reindexar: os vetores ja gravados nao mudam."""
    return Bm25SparseEmbeddingGateway(**bm25_parameters())


def bm25_parameters() -> dict[str, float]:
    return {
        "k1": _float_env("BM25_K1", DEFAULT_BM25_K1),
        "b": _float_env("BM25_B", DEFAULT_BM25_B),
        "average_length": _float_env(
            "BM25_AVG_LENGTH", DEFAULT_BM25_AVERAGE_LENGTH
        ),
    }


def reranker_model_name() -> str:
    return os.getenv("RERANKER_MODEL_NAME", "").strip() or DEFAULT_RERANKER_MODEL


@lru_cache(maxsize=1)
def build_reranker_gateway() -> CrossEncoderRerankerGateway:
    return CrossEncoderRerankerGateway(model_name=reranker_model_name())


def retrieval_settings() -> RetrievalSettings:
    """Parametros da SPEC-003; os padroes estao em ``RetrievalSettings``."""
    defaults = RetrievalSettings()
    return RetrievalSettings(
        candidates=_int_env("RETRIEVAL_CANDIDATES", defaults.candidates),
        top_n=_int_env("RERANK_TOP_N", defaults.top_n),
        min_score=_float_env("RELEVANCE_MIN_SCORE", defaults.min_score),
        context_token_budget=_int_env(
            "CONTEXT_TOKEN_BUDGET", defaults.context_token_budget
        ),
        history_token_budget=_int_env(
            "HISTORY_TOKEN_BUDGET", defaults.history_token_budget
        ),
    )


@lru_cache(maxsize=1)
def build_document_chunker() -> StructuralDocumentChunker:
    """``CHUNK_MAX_TOKENS`` vazio significa o limite do modelo carregado."""
    token_counter = build_token_counter()
    return StructuralDocumentChunker(
        token_counter=token_counter,
        max_tokens=_int_env("CHUNK_MAX_TOKENS", token_counter.max_tokens),
        overlap_sentences=_int_env(
            "CHUNK_OVERLAP_SENTENCES", DEFAULT_OVERLAP_SENTENCES
        ),
        max_prefix_tokens=_int_env(
            "CHUNK_PREFIX_MAX_TOKENS", DEFAULT_PREFIX_MAX_TOKENS
        ),
    )


@lru_cache(maxsize=1)
def build_document_indexer() -> DocumentIndexer:
    return DocumentIndexer(
        extractor=SupportedDocumentExtractor(),
        chunker=build_document_chunker(),
        embedding_gateway=build_embedding_gateway(),
        sparse_embedding_gateway=build_sparse_embedding_gateway(),
    )


def build_file_storage() -> LocalDocumentFileStorage:
    return LocalDocumentFileStorage(
        base_dir=os.getenv("DOCUMENTS_DIR", "").strip() or DEFAULT_DOCUMENTS_DIR
    )


def max_file_bytes() -> int:
    return _int_env("DOCUMENT_MAX_FILE_BYTES", DEFAULT_MAX_FILE_BYTES)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number.") from exc
