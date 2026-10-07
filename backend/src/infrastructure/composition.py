"""Montagem dos adaptadores de indexacao a partir das variaveis de ambiente.

Usada pelos pontos de entrada (API e comando de avaliacao), para que ambos
indexem com exatamente o mesmo pipeline.
"""

from __future__ import annotations

import os
from functools import lru_cache

from src.application.services import DocumentIndexer
from src.infrastructure.chunking import StructuralDocumentChunker
from src.infrastructure.documents import SupportedDocumentExtractor
from src.infrastructure.embeddings import (
    SentenceTransformerEmbeddingGateway,
    SentenceTransformerTokenCounter,
)
from src.infrastructure.storage import LocalDocumentFileStorage

DEFAULT_EMBEDDING_MODEL = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
DEFAULT_VECTOR_SIZE = 384
DEFAULT_OVERLAP_SENTENCES = 1
DEFAULT_PREFIX_MAX_TOKENS = 32
DEFAULT_MAX_FILE_BYTES = 20 * 1024 * 1024
DEFAULT_DOCUMENTS_DIR = "/app/data/documents"


def embedding_model_name() -> str:
    return os.getenv("EMBEDDING_MODEL_NAME", "").strip() or DEFAULT_EMBEDDING_MODEL


@lru_cache(maxsize=1)
def build_embedding_gateway() -> SentenceTransformerEmbeddingGateway:
    return SentenceTransformerEmbeddingGateway(
        model_name=embedding_model_name(),
        expected_dimension=_int_env("EMBEDDING_VECTOR_SIZE", DEFAULT_VECTOR_SIZE),
    )


@lru_cache(maxsize=1)
def build_document_chunker() -> StructuralDocumentChunker:
    """``CHUNK_MAX_TOKENS`` vazio significa o limite do modelo carregado."""
    token_counter = SentenceTransformerTokenCounter(
        model_name=embedding_model_name()
    )
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
