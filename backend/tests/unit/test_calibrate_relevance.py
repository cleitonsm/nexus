"""CT-22: varredura da nota minima de relevancia, sem LLM."""

from __future__ import annotations

import unittest

from chat_doubles import ScriptedReranker, ScriptedVectorStore, build_retriever, hit
from src.application.services import RetrievalSettings
from src.application.use_cases import (
    CalibrateRelevanceInput,
    CalibrateRelevanceUseCase,
)
from src.cli.calibration_report import format_report, to_dict
from src.domain import AssistantId, Document, DocumentId, EvaluationItem


class _Documents:
    def __init__(self, documents: list[Document]) -> None:
        self._documents = documents

    def list_by_assistant(self, assistant_id: AssistantId) -> list[Document]:
        return list(self._documents)


def _document(document_id: str, name: str) -> Document:
    return Document(
        id=DocumentId(document_id),
        assistant_id=AssistantId("assistant-1"),
        source_name=name,
        content_hash="hash",
    )


def _inside(item_id: str, source: str) -> EvaluationItem:
    return EvaluationItem(
        id=item_id,
        question=f"pergunta {item_id}",
        expected_answer="resposta",
        source_documents=(source,),
        validated_by="curador",
    )


def _outside(item_id: str) -> EvaluationItem:
    return EvaluationItem(
        id=item_id,
        question=f"fora {item_id}",
        out_of_scope=True,
        validated_by="curador",
    )


def _use_case(results, scores, settings=None) -> CalibrateRelevanceUseCase:
    return CalibrateRelevanceUseCase(
        document_repository=_Documents(
            [_document("d1", "a.md"), _document("d2", "b.md")]
        ),
        context_retriever=build_retriever(
            ScriptedVectorStore(results),
            reranker=ScriptedReranker(scores),
            settings=settings or RetrievalSettings(),
        ),
    )


class CalibrateRelevanceTests(unittest.TestCase):
    def _report(self, thresholds=(0.3, 0.5, 0.7)):
        results = [
            [hit("d1", "t1"), hit("d2", "t2")],  # dentro: fonte a.md
            [hit("d2", "t3")],  # dentro: fonte a.md ausente
            [hit("d2", "t4")],  # fora do escopo
            [],  # fora do escopo sem candidatos
        ]
        scores = {"t1": 0.8, "t2": 0.9, "t3": 0.6, "t4": 0.4}
        return _use_case(results, scores).execute(
            CalibrateRelevanceInput(
                assistant_id="assistant-1",
                items=(
                    _inside("i1", "a.md"),
                    _inside("i2", "a.md"),
                    _outside("o1"),
                    _outside("o2"),
                ),
                thresholds=thresholds,
            )
        )

    def test_scores_use_only_expected_source_for_in_scope(self) -> None:
        items = {item.item_id: item for item in self._report().items}
        self.assertEqual(items["i1"].source_score, 0.8)
        self.assertEqual(items["i1"].top_score, 0.9)
        self.assertIsNone(items["i2"].source_score)
        self.assertEqual(items["o1"].top_score, 0.4)
        self.assertIsNone(items["o2"].top_score)

    def test_sweep_counts_answered_and_refused(self) -> None:
        points = {p.threshold: p for p in self._report().points}
        self.assertEqual(points[0.3].answered_in_scope, 0.5)
        self.assertEqual(points[0.3].refused_out_of_scope, 0.5)
        self.assertEqual(points[0.5].refused_out_of_scope, 1.0)
        self.assertEqual(points[0.7].answered_in_scope, 0.5)
        self.assertEqual(points[0.7].balanced, 0.75)

    def test_best_prefers_lowest_threshold_on_tie(self) -> None:
        report = self._report()
        self.assertEqual(report.best.threshold, 0.5)

    def test_reports_current_threshold_and_never_changes_it(self) -> None:
        report = self._report()
        self.assertEqual(report.current_threshold, 0.5)

    def test_follow_up_items_are_left_out_of_the_sweep(self) -> None:
        follow_up = EvaluationItem(
            id="c1",
            question="E o prazo?",
            expected_answer="resposta",
            source_documents=("a.md",),
            validated_by="curador",
            history=(("user", "pergunta anterior"),),
        )
        report = _use_case([[hit("d1", "t1")]], {"t1": 0.8}).execute(
            CalibrateRelevanceInput(
                assistant_id="assistant-1",
                items=(follow_up, _inside("i1", "a.md")),
                thresholds=(0.5,),
            )
        )
        self.assertEqual([item.item_id for item in report.items], ["i1"])
        with self.assertRaises(ValueError):
            _use_case([], {}).execute(
                CalibrateRelevanceInput(
                    assistant_id="assistant-1", items=(follow_up,), thresholds=(0.5,)
                )
            )

    def test_requires_items_and_thresholds(self) -> None:
        use_case = _use_case([], {})
        with self.assertRaises(ValueError):
            use_case.execute(
                CalibrateRelevanceInput(assistant_id="assistant-1", items=())
            )
        with self.assertRaises(ValueError):
            use_case.execute(
                CalibrateRelevanceInput(
                    assistant_id="assistant-1",
                    items=(_outside("o1"),),
                    thresholds=(),
                )
            )

    def test_only_out_of_scope_items_have_no_answer_rate(self) -> None:
        report = _use_case([[hit("d1", "t1")]], {"t1": 0.2}).execute(
            CalibrateRelevanceInput(
                assistant_id="assistant-1",
                items=(_outside("o1"),),
                thresholds=(0.5,),
            )
        )
        self.assertIsNone(report.points[0].answered_in_scope)
        self.assertEqual(report.points[0].balanced, 1.0)

    def test_format_and_json_are_consistent(self) -> None:
        report = self._report()
        text = format_report(report)
        self.assertIn("<- atual", text)
        self.assertIn("i2", text)
        data = to_dict(report)
        self.assertEqual(data["best_threshold"], 0.5)
        self.assertEqual(len(data["points"]), 3)


if __name__ == "__main__":
    unittest.main()
