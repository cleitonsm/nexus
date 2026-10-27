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

    def test_text_files_are_uploaded_too(self) -> None:
        """SPEC-012: o regulamento ficticio do conjunto normativo e ``.txt``."""
        (self.seed_dir / "regulamento.txt").write_text("Art. 1º Texto.", encoding="utf-8")
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
            pass
        self.assertIn("regulamento.txt", sent)

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


class SeedWithOtherWorkerTestCase(IndexingTestCase):
    """V3 (2026-10-20): com o worker da pilha no ar, ele reserva parte dos jobs."""

    def setUp(self) -> None:
        super().setUp()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.seed_dir = Path(directory.name)
        (self.seed_dir / "a.md").write_text("# A\n\nPolitica de ferias.\n", encoding="utf-8")
        (self.seed_dir / "b.md").write_text("# B\n\nPolitica de home office.\n", encoding="utf-8")
        self.now = 0.0
        self.sleeps: list[float] = []

    def _clock(self) -> float:
        return self.now

    def _sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def _seed(self, statuses, process_pending=lambda: None, wait_seconds=600):
        s = self.scenario
        return seed_documents(
            [self.seed_dir],
            "a1",
            upload=lambda name, content: s.upload(
                source_name=name, document_id=name, raw_content=content
            ),
            process_pending=process_pending,
            current_status=statuses,
            wait_seconds=wait_seconds,
            poll_seconds=3,
            clock=self._clock,
            sleep=self._sleep,
        )

    def test_documents_indexed_by_another_worker_count(self) -> None:
        reads = {"a.md": ["processando", "indexado"], "b.md": ["indexado"]}

        def statuses(document_id: str) -> str:
            values = reads[document_id]
            return values.pop(0) if len(values) > 1 else values[0]

        self.assertEqual(self._seed(statuses), 2)
        self.assertEqual(self.sleeps, [3])

    def test_mixed_local_and_other_worker(self) -> None:
        s = self.scenario
        processed: list[str] = []

        def process_once():
            if processed:
                return None
            outcome = s.process()
            processed.append(outcome.document_id)
            return outcome

        def statuses(document_id: str) -> str:
            # o primeiro foi processado aqui; o outro, pelo worker da pilha
            return "indexado"

        self.assertEqual(self._seed(statuses, process_pending=process_once), 2)
        self.assertEqual(len(processed), 1)

    def test_retry_that_becomes_available_is_processed_here(self) -> None:
        s = self.scenario
        rounds = {"n": 0}

        def process_later():
            rounds["n"] += 1
            return s.process() if rounds["n"] >= 2 else None

        self.assertEqual(self._seed(lambda _id: "pendente", process_pending=process_later), 2)

    def test_failure_seen_in_the_database_is_reported(self) -> None:
        def statuses(document_id: str) -> str:
            return "falhou" if document_id == "b.md" else "indexado"

        with self.assertRaises(SeedDocumentsError) as caught:
            self._seed(statuses)
        self.assertIn("b.md", str(caught.exception))
        self.assertEqual(self.sleeps, [])

    def test_gives_up_after_the_job_timeout(self) -> None:
        with self.assertRaises(SeedDocumentsError) as caught:
            self._seed(lambda _id: "processando", wait_seconds=9)
        self.assertIn("fila nao processada por completo", str(caught.exception))
        self.assertEqual(sum(self.sleeps), 9)


if __name__ == "__main__":
    unittest.main()
