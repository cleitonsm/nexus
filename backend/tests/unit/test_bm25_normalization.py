"""SPEC-20261026-012: normalizacao juridica da busca esparsa (CT-92, D5)."""

from __future__ import annotations

import unittest

from src.infrastructure.embeddings import Bm25SparseEmbeddingGateway
from src.infrastructure.embeddings.bm25_sparse_embedding import tokenize


class LegalTokenizationTestCase(unittest.TestCase):
    def test_document_and_question_share_the_article_terms(self) -> None:
        document = tokenize("Art. 5º Todos são iguais perante a lei")
        for question in ("Explique o artigo 5", "art. 5º", "Art 5o", "ARTIGO 5"):
            with self.subTest(question=question):
                terms = tokenize(question)
                self.assertIn("art", terms)
                self.assertIn("5", terms)
                self.assertTrue({"art", "5"} <= set(document))

    def test_ordinals_lose_the_marker(self) -> None:
        self.assertEqual(tokenize("1º 2ª 3° 4o"), ["1", "2", "3", "4"])

    def test_paragraph_spellings(self) -> None:
        self.assertEqual(tokenize("§ 2º"), ["par", "2"])
        self.assertEqual(tokenize("parágrafo 2"), ["par", "2"])
        self.assertEqual(tokenize("parágrafos"), ["par"])
        self.assertEqual(tokenize("Parágrafo único"), ["par", "unico"])

    def test_items_and_letters_are_kept(self) -> None:
        self.assertEqual(tokenize("inciso XI alínea b"), ["inciso", "xi", "alinea", "b"])

    def test_words_that_only_look_like_ordinals_are_kept(self) -> None:
        self.assertEqual(tokenize("arte artista"), ["arte", "artista"])
        self.assertEqual(tokenize("NR-35"), ["nr", "35", "nr-35"])

    def test_article_with_letter_suffix_keeps_the_compound(self) -> None:
        self.assertEqual(tokenize("Art. 5º-A"), ["art", "5", "5-a"])

    def test_query_and_document_vectors_overlap_on_the_article(self) -> None:
        gateway = Bm25SparseEmbeddingGateway()
        document = gateway.embed_documents(["Art. 5º Todos são iguais"])[0]
        query = gateway.embed_query("Explique o artigo 5")
        self.assertGreaterEqual(len(set(document.indices) & set(query.indices)), 2)


if __name__ == "__main__":
    unittest.main()
