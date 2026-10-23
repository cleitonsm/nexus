"""V6: verificador das metas de qualidade sobre os relatorios da avaliacao."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "check_eval_reports", ROOT / "scripts" / "validation" / "check_eval_reports.py"
)
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)

GOOD = {
    "recall_at_k": 0.95,
    "mrr": 0.88,
    "faithfulness": 0.93,
    "fallback_accuracy": 0.95,
    "citation_coverage": 1.0,
}


class CheckEvalReportsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.dir = Path(directory.name)
        (self.dir / "calibracao.json").write_text("{}", encoding="utf-8")

    def _write(
        self, name: str, validated: bool = True, model: str = "gemini-3.8-flash", **metrics
    ) -> None:
        uncited = metrics.pop("uncited_generated", 0)
        items = [
            {"out_of_scope": False, "fallback_used": False, "cited": n >= uncited}
            for n in range(10)
        ]
        # Fallback no escopo nao e resposta gerada: nao conta para o RF-37.
        items.append({"out_of_scope": False, "fallback_used": True, "cited": False})
        body = {
            "validated": validated,
            "metrics": {**GOOD, **metrics},
            "parameters": {"llm_model": model},
            "items": items,
        }
        (self.dir / f"{name}.json").write_text(json.dumps(body), encoding="utf-8")

    def _run(self, *args: str) -> int:
        return check.main([str(self.dir), *args])

    def test_three_good_runs_pass(self) -> None:
        for n in range(3):
            self._write(f"2026102{n}-000000-abc")
        self.assertEqual(self._run("--runs", "3"), 0)

    def test_missing_generation_is_invalid_not_approved(self) -> None:
        self._write("20261020-000000-abc", faithfulness=None)
        self.assertEqual(self._run("--runs", "1", "--only-generation"), 2)

    def test_unvalidated_dataset_is_invalid(self) -> None:
        self._write("20261020-000000-abc", validated=False)
        self.assertEqual(self._run("--runs", "1"), 2)

    def test_fewer_reports_than_runs_is_invalid(self) -> None:
        self._write("20261020-000000-abc")
        self.assertEqual(self._run("--runs", "3"), 2)

    def test_faithfulness_mean_and_minimum(self) -> None:
        self._write("20261020-000001-abc", faithfulness=0.95)
        self._write("20261020-000002-abc", faithfulness=0.95)
        self._write("20261020-000003-abc", faithfulness=0.87)  # abaixo de 0,88
        self.assertEqual(self._run("--runs", "3"), 1)

    def test_each_goal_is_checked(self) -> None:
        for metric, value in (
            ("recall_at_k", 0.79),
            ("fallback_accuracy", 0.85),
            ("uncited_generated", 1),
        ):
            with self.subTest(metric=metric):
                for path in self.dir.glob("2026*.json"):
                    path.unlink()
                self._write("20261020-000000-abc", **{metric: value})
                self.assertEqual(self._run("--runs", "1"), 1)

    def test_other_model_than_the_official_one_is_invalid(self) -> None:
        self._write("20261021-000000-abc", model="modelo-simulado")
        self.assertEqual(self._run("--runs", "1", "--model", "gemini-3.8-flash"), 2)
        self.assertEqual(self._run("--runs", "1", "--only-generation"), 0)

    def test_fallback_inside_scope_does_not_break_rf37(self) -> None:
        """Decisao do autor (2026-10-21): a taxa de resposta (citation_coverage) e informativa."""
        self._write("20261021-000000-abc", citation_coverage=0.935)
        self.assertEqual(self._run("--runs", "1"), 0)

    def test_calibration_file_is_ignored(self) -> None:
        self._write("20261020-000000-abc")
        self.assertEqual(self._run("--runs", "1"), 0)


if __name__ == "__main__":
    unittest.main()
