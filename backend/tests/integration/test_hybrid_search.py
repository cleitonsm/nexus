"""CT-18 e CT-19 (SPEC-20261007-003): busca hibrida e reranking locais.

Exige o Qdrant do Compose e os modelos locais (cache ou primeiro download).
Execute dentro do container do backend.
"""

from __future__ import annotations

import os
import unittest
from uuid import uuid4

from src.application.services import ContextRetriever, RetrievalSettings
from src.domain import (
    AssistantId,
    CollectionName,
    DocumentId,
    IndexOutdatedError,
    SearchResult,
    VectorChunk,
)
from src.infrastructure.composition import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_RERANKER_MODEL,
)
from src.infrastructure.embeddings import (
    Bm25SparseEmbeddingGateway,
    SentenceTransformerEmbeddingGateway,
)

try:
    import sentence_transformers  # noqa: F401
    from qdrant_client.http import models

    from src.infrastructure.reranking import CrossEncoderRerankerGateway
    from src.infrastructure.vector_store import QdrantVectorStoreGateway
except ImportError:  # pragma: no cover
    sentence_transformers = None

EMBEDDING_MODEL = (
    os.getenv("EMBEDDING_MODEL_NAME", "").strip() or DEFAULT_EMBEDDING_MODEL
)
RERANKER_MODEL = (
    os.getenv("RERANKER_MODEL_NAME", "").strip() or DEFAULT_RERANKER_MODEL
)

# Um unico trecho menciona "NR-35"; os demais falam de seguranca em termos
# parecidos, para que a busca densa sozinha nao baste.
TARGET = (
    "Trabalhos acima de dois metros exigem o treinamento previsto na NR-35 "
    "e o uso de cinto de seguranca."
)
DOCUMENTS = [
    "O uso de capacete é obrigatório em todo o canteiro de obras.",
    "Os extintores são inspecionados a cada mês pela brigada.",
    "As férias podem ser divididas em até três períodos.",
    "O reembolso de despesas é feito em até dez dias úteis.",
    "A norma interna de segurança exige luvas no almoxarifado.",
    "Visitantes precisam de crachá e de acompanhamento na fábrica.",
    "O treinamento de integração dura dois dias para novos colaboradores.",
    "Equipamentos de proteção devem ser devolvidos no desligamento.",
    TARGET,
    "A CIPA se reúne mensalmente para tratar de prevenção de acidentes.",
    "O estacionamento funciona das 7h às 22h.",
    "As saídas de emergência devem permanecer desobstruídas.",
]


def _qdrant() -> "QdrantVectorStoreGateway | None":
    if sentence_transformers is None:
        return None
    gateway = QdrantVectorStoreGateway(
        url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
        api_key=os.getenv("QDRANT_API_KEY", "") or None,
    )
    try:
        gateway.collection_exists(CollectionName("nexus-connectivity-check"))
    except Exception:  # noqa: BLE001 - qualquer falha de conexao pula o teste
        return None
    return gateway


class HybridSearchTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        gateway = _qdrant()
        if gateway is None:
            raise unittest.SkipTest("Qdrant ou modelos locais indisponiveis")
        cls.gateway = gateway
        cls.embedding = SentenceTransformerEmbeddingGateway(
            model_name=EMBEDDING_MODEL,
            expected_dimension=384,
        )
        cls.sparse = Bm25SparseEmbeddingGateway()
        cls.reranker = CrossEncoderRerankerGateway(model_name=RERANKER_MODEL)
        cls.assistant_id = AssistantId(f"teste-hibrida-{uuid4().hex[:12]}")
        cls.alias = CollectionName.from_assistant_id(cls.assistant_id)
        cls.collection = CollectionName.versioned(cls.assistant_id, 1)
        gateway.ensure_collection(cls.collection, vector_size=384)
        gateway.point_alias(cls.alias, cls.collection)
        dense = cls.embedding.embed_documents(DOCUMENTS)
        sparse = cls.sparse.embed_documents(DOCUMENTS)
        gateway.upsert_chunks(
            cls.collection,
            [
                VectorChunk(
                    id=f"doc-{index % 2}:{index}",
                    document_id=DocumentId(f"doc-{index % 2}"),
                    assistant_id=cls.assistant_id,
                    chunk_index=index,
                    source_name=f"manual-{index % 2}.pdf",
                    content_hash="hash",
                    text=text,
                    vector=dense[index],
                    section_path="Seguranca > Normas",
                    page=index + 1,
                    embedding_model=EMBEDDING_MODEL,
                    pipeline_version="3",
                    sparse_vector=sparse[index],
                )
                for index, text in enumerate(DOCUMENTS)
            ],
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.gateway.delete_collection(cls.collection)

    def _retriever(self, **settings: object) -> ContextRetriever:
        return ContextRetriever(
            embedding_gateway=self.embedding,
            sparse_embedding_gateway=self.sparse,
            vector_store_gateway=self.gateway,
            reranker_gateway=self.reranker,
            settings=RetrievalSettings(**settings),
        )

    def _search(self, query: str, limit: int = 12, **kwargs) -> list[SearchResult]:
        return self.gateway.hybrid_search(
            self.alias,
            self.embedding.embed_query(query),
            self.sparse.embed_query(query),
            limit,
            **{"user_groups": None, **kwargs},
        )

    def test_exact_term_is_among_the_top_five_after_reranking(self) -> None:
        """CT-18 / cenario "Recuperar termo exato"."""
        retriever = self._retriever()
        query = "o que diz a NR-35?"
        ranked = retriever.rerank(
            query,
            retriever.search(self.assistant_id, query, user_groups=None),
        )
        self.assertLessEqual(len(ranked), 5)
        self.assertIn(TARGET, [item.text for item in ranked])

    def test_sparse_prefetch_alone_finds_the_exact_term(self) -> None:
        """O vetor esparso e o IDF do Qdrant funcionam sem a parte densa."""
        response = self.gateway._client.query_points(  # noqa: SLF001
            collection_name=self.alias.value,
            query=models.SparseVector(
                indices=list(self.sparse.embed_query("NR-35").indices),
                values=list(self.sparse.embed_query("NR-35").values),
            ),
            using="sparse",
            limit=1,
            with_payload=True,
        )
        self.assertEqual(response.points[0].payload["text"], TARGET)

    def test_results_carry_source_section_and_page(self) -> None:
        hits = self._search("NR-35", limit=3)
        target = next(item for item in hits if item.text == TARGET)
        self.assertEqual(target.source_name, "manual-0.pdf")
        self.assertEqual(target.section_path, "Seguranca > Normas")
        self.assertEqual(target.page, 9)
        self.assertEqual(target.chunk_id, "doc-0:8")

    def test_payload_filter_restricts_the_candidates(self) -> None:
        hits = self._search(
            "seguranca", payload_filter={"document_id": "doc-1"}
        )
        self.assertTrue(hits)
        self.assertEqual({item.document_id.value for item in hits}, {"doc-1"})

    def test_query_without_sparse_terms_still_searches(self) -> None:
        self.assertTrue(self.sparse.embed_query("o que é?").is_empty)
        self.assertTrue(self._search("o que é?", limit=3))

    def test_unknown_collection_returns_no_candidates(self) -> None:
        missing = CollectionName(f"assistant-inexistente-{uuid4().hex[:8]}")
        hits = self.gateway.hybrid_search(
            missing,
            self.embedding.embed_query("x"),
            self.sparse.embed_query("x"),
            3,
            user_groups=None,
        )
        self.assertEqual(hits, [])

    def _phase_two_collection(self, vector_size: int) -> CollectionName:
        """Collection da Fase 2: um unico vetor, sem nome."""
        legacy = CollectionName(f"assistant-fase2-{uuid4().hex[:8]}-v1")
        self.gateway._client.create_collection(  # noqa: SLF001
            collection_name=legacy.value,
            vectors_config=models.VectorParams(
                size=vector_size, distance=models.Distance.COSINE
            ),
        )
        self.addCleanup(self.gateway.delete_collection, legacy)
        return legacy

    def test_phase_two_collection_is_searched_by_the_dense_vector_only(
        self,
    ) -> None:
        """Ate a reindexacao o chat continua, sem a parte esparsa."""
        legacy = self._phase_two_collection(vector_size=384)
        self.gateway._client.upsert(  # noqa: SLF001
            collection_name=legacy.value,
            points=[
                models.PointStruct(
                    id=index,
                    vector=self.embedding.embed_documents([text])[0],
                    payload={
                        "chunk_id": f"doc:{index}",
                        "document_id": "doc",
                        "text": text,
                        "source_name": "antigo.md",
                    },
                )
                for index, text in enumerate(DOCUMENTS[:4])
            ],
            wait=True,
        )
        query = "de quanto em quanto tempo os extintores são verificados?"
        with self.assertLogs(
            "src.infrastructure.vector_store.qdrant_store", level="WARNING"
        ):
            hits = self.gateway.hybrid_search(
                legacy,
                self.embedding.embed_query(query),
                self.sparse.embed_query(query),
                2,
                user_groups=None,
            )
        self.assertEqual(len(hits), 2)
        self.assertIn("extintores", hits[0].text)
        self.assertEqual(hits[0].source_name, "antigo.md")

    def test_collection_of_another_dimension_asks_for_reindex(self) -> None:
        legacy = self._phase_two_collection(vector_size=8)
        with self.assertRaises(IndexOutdatedError):
            self.gateway.hybrid_search(
                legacy,
                self.embedding.embed_query("x"),
                self.sparse.embed_query("x"),
                3,
                user_groups=None,
            )

    def test_reranker_orders_candidates_and_keeps_top_n(self) -> None:
        """CT-19: notas entre 0 e 1, ordem decrescente, N melhores."""
        query = "de quanto em quanto tempo os extintores são verificados?"
        candidates = self._search(query)
        ranked_all = self.reranker.rerank(query, candidates)
        scores = [item.score for item in ranked_all]
        self.assertEqual(len(ranked_all), len(candidates))
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(all(0.0 <= score <= 1.0 for score in scores))
        self.assertIn("extintores", ranked_all[0].text)

        top = self._retriever(top_n=3).rerank(query, candidates)
        self.assertEqual([item.text for item in top], [
            item.text for item in ranked_all[:3]
        ])

    def test_reranker_scores_unrelated_passage_below_related_one(self) -> None:
        query = "qual o horário do estacionamento?"
        related, unrelated = self.reranker.rerank(
            query,
            [
                SearchResult("a", DocumentId("d"), 0.0, DOCUMENTS[10]),
                SearchResult("b", DocumentId("d"), 0.0, DOCUMENTS[1]),
            ],
        )
        self.assertEqual(related.text, DOCUMENTS[10])
        self.assertGreater(related.score, unrelated.score)


if __name__ == "__main__":
    unittest.main()
