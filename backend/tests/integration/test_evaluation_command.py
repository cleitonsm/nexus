"""CT-04 (RF-25, RF-26, RN-14): o comando de avaliacao de ponta a ponta.

``python -m src.cli.evaluate --no-generation`` sobre um conjunto minimo gera
os relatorios JSON e Markdown com commit, modelos e parametros; uma regressao
simulada termina com codigo de saida 1. Exige PostgreSQL e Qdrant do Compose
(execute dentro do container do backend); sem eles, o teste e pulado. Nao usa
LLM. O assistente criado tem nome unico e e removido ao final.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

QUESTIONS = [
    {
        "id": "q1",
        "question": "Quantos dias de ferias o colaborador tem por ano?",
        "expected_answer": "Trinta dias corridos.",
        "source_documents": ["ferias.md"],
        "out_of_scope": False,
        "validated_by": "teste",
    },
    {
        "id": "q2",
        "question": "Como pedir reembolso de viagem?",
        "expected_answer": "Pelo sistema financeiro, com nota fiscal.",
        "source_documents": ["reembolso.md"],
        "out_of_scope": False,
        "validated_by": "teste",
    },
]
DOCUMENTS = {
    "ferias.md": "# Ferias\n\nO colaborador tem trinta dias corridos de ferias por ano.\n",
    "reembolso.md": "# Reembolso\n\nO reembolso de viagem e pedido no sistema financeiro, com nota fiscal.\n",
}


def _qdrant():
    from src.infrastructure.vector_store import QdrantVectorStoreGateway

    return QdrantVectorStoreGateway(
        url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
        api_key=os.getenv("QDRANT_API_KEY", "") or None,
    )


def _services_available() -> bool:
    try:
        from sqlalchemy import text

        from src.infrastructure.composition import build_embedding_gateway  # noqa: F401
        from src.infrastructure.database import SessionLocal, run_migrations

        run_migrations()
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        from src.domain import CollectionName

        _qdrant().collection_exists(CollectionName("nexus-connectivity-check"))
    except Exception:  # noqa: BLE001 - servicos indisponiveis pulam o teste
        return False
    return True


class EvaluationCommandTestCase(unittest.TestCase):
    def setUp(self) -> None:
        if not _services_available():
            self.skipTest("PostgreSQL ou Qdrant indisponivel")
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.seed = self.root / "seed"
        self.seed.mkdir()
        for name, text in DOCUMENTS.items():
            (self.seed / name).write_text(text, encoding="utf-8")
        self.dataset = self.root / "dataset-teste.jsonl"
        self.dataset.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in QUESTIONS) + "\n",
            encoding="utf-8",
        )
        self.reports = self.root / "reports"
        self.assistant_name = f"Avaliacao CT-04 {uuid4().hex[:8]}"
        self.addCleanup(self._remove_assistant)
        self._previous_commit = os.environ.get("GIT_COMMIT")
        os.environ["GIT_COMMIT"] = "ct04"
        self.addCleanup(self._restore_commit)

    def _restore_commit(self) -> None:
        if self._previous_commit is None:
            os.environ.pop("GIT_COMMIT", None)
        else:
            os.environ["GIT_COMMIT"] = self._previous_commit

    def _remove_assistant(self) -> None:
        from src.application.services import read_index_state
        from src.infrastructure.database import PostgresAssistantRepository, SessionLocal

        with SessionLocal() as session:
            repository = PostgresAssistantRepository(session=session)
            for assistant in repository.list_all():
                if assistant.name.value == self.assistant_name:
                    state = read_index_state(_qdrant(), assistant.id)
                    if state.current is not None:
                        _qdrant().delete_collection(state.current)
                    repository.delete(assistant.id)

    def _evaluate(self) -> int:
        from src.cli.evaluate import main

        return main(
            [
                "--dataset", str(self.dataset),
                "--reports-dir", str(self.reports),
                "--seed-dir", str(self.seed),
                "--assistant-name", self.assistant_name,
                "--no-generation",
            ]
        )

    def _latest(self) -> Path:
        return sorted((self.reports / self.dataset.stem).glob("*.json"))[-1]

    def test_report_records_commit_models_and_parameters(self) -> None:
        self.assertEqual(self._evaluate(), 0)
        report_path = self._latest()
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["parameters"]["commit"], "ct04")
        for key in ("embedding", "reranker", "retrieval_candidates", "pipeline_version"):
            self.assertTrue(report["parameters"].get(key), key)
        self.assertGreater(report["metrics"]["recall_at_k"], 0)
        self.assertIsNone(report["metrics"]["faithfulness"])
        markdown = report_path.with_suffix(".md").read_text(encoding="utf-8")
        self.assertIn("recall_at_k", markdown)
        self.assertIn("ct04", report_path.name)

    def test_simulated_regression_ends_with_exit_code_one(self) -> None:
        self.assertEqual(self._evaluate(), 0)
        baseline = json.loads(self._latest().read_text(encoding="utf-8"))
        # Metricas impossiveis de igualar, em relatorio mais recente que qualquer real.
        impossible = dict(baseline, metrics={**baseline["metrics"], "recall_at_k": 1.5, "mrr": 1.5})
        (self.reports / self.dataset.stem / "99999999-999999-baseline.json").write_text(
            json.dumps(impossible), encoding="utf-8"
        )
        self.assertEqual(self._evaluate(), 1)


if __name__ == "__main__":
    unittest.main()
