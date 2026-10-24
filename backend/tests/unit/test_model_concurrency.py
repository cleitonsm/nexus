"""Ensaio do RNF-01 (2026-10-24): perguntas simultaneas no chat falhavam com
``RuntimeError: Already borrowed`` (tokenizador rapido usado por duas threads).

Os adaptadores locais enfileiram as chamadas ao mesmo modelo. Os modelos falsos
abaixo levantam o mesmo erro se forem chamados ao mesmo tempo.
"""

from __future__ import annotations

import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from src.domain import DocumentId, SearchResult
from src.infrastructure.embeddings import sentence_transformer_embedding as embedding_module
from src.infrastructure.reranking import cross_encoder_reranker as reranker_module


class _NotReentrant:
    def __init__(self) -> None:
        self._busy = threading.Lock()

    def _enter(self) -> None:
        if not self._busy.acquire(blocking=False):
            raise RuntimeError("Already borrowed")
        time.sleep(0.02)
        self._busy.release()


class FakeSentenceModel(_NotReentrant):
    max_seq_length = 128

    def get_sentence_embedding_dimension(self) -> int:
        return 3

    def encode(self, texts, **kwargs):
        self._enter()
        return [[0.1, 0.2, 0.3] for _ in texts]

    def tokenizer(self, text, **kwargs):
        self._enter()
        return {"input_ids": text.split()}


class FakeCrossEncoder(_NotReentrant):
    def predict(self, pairs, **kwargs):
        self._enter()
        return [0.5 for _ in pairs]


def _parallel(call, times: int = 12) -> list:
    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(lambda _: call(), range(times)))


class ModelConcurrencyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        embedding_module._model_lock.cache_clear()
        reranker_module._model_lock.cache_clear()
        self.addCleanup(embedding_module._model_lock.cache_clear)
        self.addCleanup(reranker_module._model_lock.cache_clear)

    def test_embedding_and_token_counter_share_one_lock_per_model(self) -> None:
        model = FakeSentenceModel()
        with mock.patch.object(embedding_module, "_load_model", return_value=model):
            gateway = embedding_module.SentenceTransformerEmbeddingGateway(
                model_name="m", expected_dimension=3
            )
            counter = embedding_module.SentenceTransformerTokenCounter(model_name="m")
            results = _parallel(
                lambda: (gateway.embed_query("a b"), counter.count("a b c"))
            )
        self.assertEqual(results[0], ([0.1, 0.2, 0.3], 3))

    def test_reranker_calls_are_serialized(self) -> None:
        candidate = SearchResult(
            chunk_id="c1", document_id=DocumentId("d1"), source_name="a.md", text="texto", score=0.0
        )
        with mock.patch.object(
            reranker_module, "_load_model", return_value=(FakeCrossEncoder(), None)
        ):
            gateway = reranker_module.CrossEncoderRerankerGateway(model_name="r")
            results = _parallel(lambda: gateway.rerank("pergunta", [candidate]))
        self.assertTrue(all(item[0].score == 0.5 for item in results))


if __name__ == "__main__":
    unittest.main()
