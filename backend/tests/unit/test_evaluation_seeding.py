"""E7: o comando de avaliacao precisa indexar os documentos do piloto.

Desde a SPEC-005 o envio so cria um documento pendente; sem processar a fila
o conjunto de avaliacao mediria uma base vazia. O comando de avaliacao
(``src.cli.evaluate``) usa ``seed_documents`` para enviar e processar.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_indexing import IndexingTestCase

from src.application.use_cases import SeedDocumentsError, seed_documents
from src.domain import DocumentStatus


class SeedDocumentsTestCase(IndexingTestCase):
    def setUp(self) -> None:
        super().setUp()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.seed_dir = Path(directory.name)
        (self.seed_dir / "a.md").write_text("# A\n\nPolitica de ferias.\n", encoding="utf-8")
        (self.seed_dir / "b.md").write_text("# B\n\nPolitica de home office.\n", encoding="utf-8")

    def _seed(self, directories=None):
        s = self.scenario
        return seed_documents(
            directories if directories is not None else [self.seed_dir],
            "a1",
            upload=lambda name, content: s.upload(
                source_name=name, document_id=name, raw_content=content
            ),
            process_pending=s.process,
        )

    def test_uploads_and_processes_every_markdown_file(self) -> None:
        indexed = self._seed()
        self.assertEqual(indexed, 2)
        documents = self.scenario.documents.items.values()
        self.assertEqual({d.status for d in documents}, {DocumentStatus.INDEXED})
        self.assertTrue(all(d.chunk_count > 0 for d in documents))

    def test_docx_files_are_uploaded_too(self) -> None:
        (self.seed_dir / "tabela.docx").write_bytes(b"PK")
        sent: list[str] = []
        s = self.scenario

        def upload(name, content):
            sent.append(name)
            return s.upload(source_name=name, document_id=name, raw_content=content)

        try:
            seed_documents(
                [self.seed_dir], "a1", upload=upload, process_pending=lambda: None
            )
        except SeedDocumentsError:
            pass  # a fila nao foi processada; so importa o que foi enviado
        self.assertEqual(sent, ["a.md", "b.md", "tabela.docx"])

    def test_failed_document_is_reported(self) -> None:
        (self.seed_dir / "c.md").write_bytes(b"\xff\xfe\x00")
        s = self.scenario
        original = s.indexer.build_chunks

        def failing(**kwargs):
            if kwargs["source_name"] == "c.md":
                raise ValueError("unreadable")
            return original(**kwargs)

        s.indexer.build_chunks = failing
        with self.assertRaises(SeedDocumentsError) as caught:
            self._seed()
        self.assertIn("c.md", str(caught.exception))

    def test_no_files_seeds_nothing(self) -> None:
        self.assertEqual(self._seed([]), 0)


if __name__ == "__main__":
    unittest.main()
