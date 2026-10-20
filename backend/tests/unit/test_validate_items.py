"""Ferramenta de validacao do conjunto de referencia (RN-15)."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "evaluation"
spec = importlib.util.spec_from_file_location("validate_items", ROOT / "validate_items.py")
validate_items = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate_items)

DATASET = ROOT / "datasets" / "nexus-docs-ampliado.jsonl"
# Itens que eram rascunho de IA ate a validacao do curador (2026-10-20); os testes da
# ferramenta recriam esse estado numa copia, sem depender do arquivo real.
DRAFT_PREFIXES = ("te-", "co-", "tb-", "pl-")
DRAFT_OUT_OF_SCOPE = {f"fora-{n:02d}" for n in range(6, 21)}


def _is_draft(item: dict) -> bool:
    return item["id"].startswith(DRAFT_PREFIXES) or item["id"] in DRAFT_OUT_OF_SCOPE


class ValidateItemsTests(unittest.TestCase):
    def _copy(self) -> Path:
        """Copia do conjunto com os 55 itens de volta ao estado de rascunho."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "dataset.jsonl"
        lines = []
        for item in validate_items.load(DATASET):
            if _is_draft(item):
                item.pop("validated_by", None)
                item["origem"] = "rascunho IA; aguarda validacao do curador"
            lines.append(json.dumps(item, ensure_ascii=False))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_draft_dataset_meets_the_plan_composition(self) -> None:
        items = validate_items.load(DATASET)
        inside = [item for item in items if not item["out_of_scope"]]
        self.assertGreaterEqual(len(items), 80)
        self.assertGreaterEqual(len(inside), 60)
        self.assertGreaterEqual(len(items) - len(inside), 20)
        self.assertGreaterEqual(sum(1 for i in items if i["id"].startswith("te-")), 8)
        self.assertGreaterEqual(sum(1 for i in items if i.get("history")), 8)
        docx = [i for i in items if any(s.endswith(".docx") for s in i.get("source_documents", []))]
        self.assertGreaterEqual(len(docx), 8)

    def test_every_source_exists_in_the_seed_directories(self) -> None:
        repo = ROOT.parents[2]
        names = {
            path.name
            for directory in (
                repo / "docs" / "negocio",
                repo / "docs" / "arquitetura",
                ROOT / "fixtures",
            )
            for path in directory.glob("*.*")
        }
        for item in validate_items.load(DATASET):
            for source in item.get("source_documents", []):
                self.assertIn(source, names, f"{item['id']}: {source}")

    def test_real_dataset_is_fully_validated(self) -> None:
        """RN-15: validado pelo curador em 2026-10-20; nenhum item volta a rascunho."""
        items = validate_items.load(DATASET)
        self.assertEqual(validate_items.pending(items), [])
        self.assertFalse([item["id"] for item in items if "origem" in item])

    def test_new_items_are_pending_and_original_ones_are_validated(self) -> None:
        items = validate_items.load(self._copy())
        waiting = {item["id"] for item in validate_items.pending(items)}
        self.assertTrue(waiting)
        self.assertNotIn("neg-01", waiting)
        self.assertIn("te-01", waiting)

    def test_approve_sets_validator_and_drops_draft_mark(self) -> None:
        path = self._copy()
        items = validate_items.load(path)
        approved = validate_items.approve(items, {"te-01", "fora-06"}, " Curadora ")
        self.assertEqual(sorted(approved), ["fora-06", "te-01"])
        by_id = {item["id"]: item for item in items}
        self.assertEqual(by_id["te-01"]["validated_by"], "Curadora")
        self.assertNotIn("origem", by_id["te-01"])
        self.assertIn("origem", by_id["te-02"])

    def test_approve_rejects_unknown_ids_and_blank_name(self) -> None:
        items = validate_items.load(self._copy())
        with self.assertRaises(ValueError):
            validate_items.approve(items, {"nao-existe"}, "Curadora")
        with self.assertRaises(ValueError):
            validate_items.approve(items, None, "  ")

    def test_cli_round_trip_makes_dataset_loadable_without_flag(self) -> None:
        from src.infrastructure.evaluation import JsonlEvaluationDatasetLoader

        path = self._copy()
        self.assertEqual(validate_items.main([str(path), "--by", "Curadora", "--approve-all"]), 0)
        items = JsonlEvaluationDatasetLoader().load(path)
        self.assertEqual(len(items), len(validate_items.load(path)))
        self.assertTrue(all(item.is_validated for item in items))

    def test_draft_loads_only_with_allow_unvalidated(self) -> None:
        from src.infrastructure.evaluation import (
            EvaluationDatasetError,
            JsonlEvaluationDatasetLoader,
        )

        draft = self._copy()
        with self.assertRaises(EvaluationDatasetError):
            JsonlEvaluationDatasetLoader().load(draft)
        items = JsonlEvaluationDatasetLoader(allow_unvalidated=True).load(draft)
        self.assertGreaterEqual(len(items), 80)
        self.assertTrue(any(item.history for item in items))


if __name__ == "__main__":
    unittest.main()
