"""CT-48 (RF-62, RN-14): a regressao simulada e detectada pela comparacao.

Reproduz, sem Docker, o que ``scripts/validation/regression-gate.sh`` faz no
ambiente: um relatorio anterior inflado vira a linha de base, e a avaliacao
atual e apontada como regressao. O script confere o codigo de saida real.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.application.use_cases import (
    CompareEvaluationReportsInput,
    CompareEvaluationReportsUseCase,
)
from src.infrastructure.evaluation.report_store import JsonEvaluationReportStore

DATASET = "nexus-docs"
CURRENT = {"recall_at_k": 0.82, "mrr": 0.71, "faithfulness": None, "fallback_accuracy": None}


class RegressionGateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.store = JsonEvaluationReportStore(self.directory)

    def tearDown(self) -> None:
        for path in sorted(self.directory.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        self.directory.rmdir()

    def _write(self, label: str, metrics: dict[str, float]) -> None:
        folder = self.directory / DATASET
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{label}.json").write_text(json.dumps({"metrics": metrics}))

    def _compare(self):
        previous = self.store.load_latest(DATASET)
        return CompareEvaluationReportsUseCase().execute(
            CompareEvaluationReportsInput(
                current=CURRENT,
                previous=previous["metrics"] if previous else None,
                tolerance=0.02,
            )
        )

    def test_inflated_baseline_turns_the_current_run_into_a_regression(self) -> None:
        self._write("20261001-120000-real", {"recall_at_k": 0.8, "mrr": 0.7})
        self._write("29991231-235959-ct48-baseline", {"recall_at_k": 1.0, "mrr": 1.0})
        comparison = self._compare()
        self.assertTrue(comparison.has_regression)
        self.assertEqual(set(comparison.regressions), {"recall_at_k", "mrr"})

    def test_drop_within_tolerance_is_not_a_regression(self) -> None:
        self._write("20261001-120000-real", {"recall_at_k": 0.835, "mrr": 0.72})
        self.assertFalse(self._compare().has_regression)

    def test_first_run_without_baseline_passes(self) -> None:
        self.assertFalse(self._compare().has_regression)


if __name__ == "__main__":
    unittest.main()
