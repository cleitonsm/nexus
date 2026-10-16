"""CT-40 (RNF-17): upload de 25 MB responde 202 em ate 2 s.

Mede no cliente o tempo ate o 202 de arquivos de 24 MB (PDF e DOCX distintos,
gerados por ``scripts/perf/corpus.py``). Exige a pilha no ar e a pasta
``scripts`` montada em ``/app/scripts`` (ou ``SCRIPTS_DIR``). A medicao
completa, com 30 amostras e percentis, e ``scripts/perf/upload_latency.py``.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from uuid import uuid4

from stack_support import Api, stack_available, token_for

LIMIT_SECONDS = 2.0
SCRIPTS_DIR = Path(os.getenv("SCRIPTS_DIR", "/app/scripts"))


class UploadLatencyTests(unittest.TestCase):
    def setUp(self) -> None:
        if not stack_available():
            self.skipTest("pilha do Compose indisponivel")
        perf = SCRIPTS_DIR / "perf"
        if not (perf / "corpus.py").exists():
            self.skipTest("scripts/perf nao montado em /app/scripts")
        sys.path.insert(0, str(perf))
        self.addCleanup(lambda: sys.path.remove(str(perf)))
        self.admin = Api(token_for("admin.nexus"))
        status, data = self.admin.json(
            "POST", "/assistants", payload={"name": f"CT-40 {uuid4().hex[:8]}"}
        )
        self.assertEqual(status, 201, data)
        self.assistant_id = data["id"]
        self.addCleanup(
            lambda: self.admin.request("DELETE", f"/assistants/{self.assistant_id}")
        )

    def test_25mb_upload_returns_202_within_limit(self) -> None:
        import corpus

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Perto do teto de 25 MiB, mas dentro dele: os geradores passam do
            # tamanho pedido, entao o alvo e calibrado pelo tamanho obtido.
            ceiling = 25 * corpus.MB - 256 * 1024
            files = [
                (
                    corpus.make_fitting(corpus.make_text_pdf, root / "a.pdf", ceiling, 11),
                    "application/pdf",
                ),
                (
                    corpus.make_fitting(corpus.make_docx, root / "b.docx", ceiling, 12),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            ]
            for path, content_type in files:
                with self.subTest(file=path.name):
                    content = path.read_bytes()
                    started = time.perf_counter()
                    status, body = self.admin.upload(
                        self.assistant_id,
                        path.name,
                        content,
                        content_type=content_type,
                    )
                    elapsed = time.perf_counter() - started
                    self.assertEqual(status, 202, body)
                    self.assertLessEqual(elapsed, LIMIT_SECONDS, f"{elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main()
