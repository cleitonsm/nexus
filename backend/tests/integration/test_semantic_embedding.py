"""CT-10 e CT-11 (SPEC-20261007-002): embeddings semanticos locais.

Exige o modelo de embedding disponivel (cache local ou primeiro download).
Execute dentro do container do backend.
"""

from __future__ import annotations

import math
import os
import socket
import unittest
from unittest.mock import patch

from src.domain import BlockType, DocumentBlock, ExtractedDocument
from src.infrastructure.chunking import StructuralDocumentChunker
from src.infrastructure.composition import DEFAULT_EMBEDDING_MODEL

try:
    import sentence_transformers  # noqa: F401
except ImportError:  # pragma: no cover
    sentence_transformers = None

from src.infrastructure.embeddings import (
    SentenceTransformerEmbeddingGateway,
    SentenceTransformerTokenCounter,
)

MODEL = os.getenv("EMBEDDING_MODEL_NAME", "").strip() or DEFAULT_EMBEDDING_MODEL

DOCUMENTS = [
    "O reembolso é feito em até 10 dias úteis.",
    "As férias podem ser divididas em até três períodos.",
    "O crachá deve ser usado em local visível durante o expediente.",
    "O estacionamento funciona das 7h às 22h.",
    "A senha da rede expira a cada noventa dias.",
    "O refeitório serve almoço das 11h30 às 14h.",
    "Visitantes precisam ser cadastrados na recepção.",
    "O plano de saúde cobre consultas e exames.",
    "As reuniões de equipe acontecem às segundas-feiras.",
    "O computador deve ser bloqueado ao sair da mesa.",
    "A biblioteca empresta até três livros por pessoa.",
    "O ar-condicionado é desligado às 20h.",
]


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


@unittest.skipIf(sentence_transformers is None, "sentence-transformers nao instalado")
class SemanticEmbeddingTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gateway = SentenceTransformerEmbeddingGateway(
            model_name=MODEL,
            expected_dimension=384,
        )
        cls.counter = SentenceTransformerTokenCounter(model_name=MODEL)

    def test_vectors_have_384_dimensions_without_network(self) -> None:
        """CT-10: com o modelo carregado, nenhuma conexao e aberta."""

        def _blocked(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("network access attempted during embedding")

        with patch.object(socket.socket, "connect", _blocked):
            vectors = self.gateway.embed_documents(DOCUMENTS[:2])
            query = self.gateway.embed_query("pergunta de teste")

        self.assertEqual([len(vector) for vector in vectors], [384, 384])
        self.assertEqual(len(query), 384)
        self.assertAlmostEqual(math.sqrt(_cosine(query, query)), 1.0, places=4)

    def test_dimension_mismatch_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SentenceTransformerEmbeddingGateway(
                model_name=MODEL,
                expected_dimension=385,
            )

    def test_paraphrase_retrieves_the_right_passage(self) -> None:
        """CT-11: parafrase recupera o trecho entre os cinco primeiros."""
        vectors = self.gateway.embed_documents(DOCUMENTS)
        query = self.gateway.embed_query(
            "quanto tempo demora para devolverem meu dinheiro?"
        )
        ranking = sorted(
            range(len(DOCUMENTS)),
            key=lambda index: _cosine(query, vectors[index]),
            reverse=True,
        )
        self.assertIn(0, ranking[:5])

    @unittest.skipUnless(MODEL == DEFAULT_EMBEDDING_MODEL, "modelo diferente da ADR 0004")
    def test_model_sequence_limit_is_128_tokens(self) -> None:
        """Confirma o limite que a SPEC-002 deixou "a confirmar"."""
        self.assertEqual(self.counter.max_tokens, 128)

    def test_token_count_includes_special_tokens_and_is_not_truncated(self) -> None:
        self.assertEqual(self.counter.count(""), 2)
        long_text = "palavra " * 400
        self.assertGreater(self.counter.count(long_text), self.counter.max_tokens)

    def test_chunks_respect_the_real_tokenizer_limit(self) -> None:
        """CT-07 com o tokenizador real."""
        paragraph = " ".join(DOCUMENTS * 6)
        chunker = StructuralDocumentChunker(
            token_counter=self.counter,
            max_tokens=self.counter.max_tokens,
            overlap_sentences=1,
            max_prefix_tokens=32,
        )
        chunks = chunker.chunk(
            ExtractedDocument(
                blocks=(
                    DocumentBlock(
                        type=BlockType.PARAGRAPH,
                        text=paragraph,
                        section_path=("Manual do Colaborador", "Regras Gerais"),
                    ),
                )
            )
        )
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(
                self.counter.count(chunk.text),
                self.counter.max_tokens,
            )


if __name__ == "__main__":
    unittest.main()
