"""SPEC-20261007-001: avaliacao e linha de base (CT-01, CT-02, CT-03)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from chat_doubles import (
    ScriptedLLM,
    ScriptedVectorStore,
    WordTokenCounter,
    build_retriever,
    hit,
)
from src.application.services import GroundedAnswerGenerator
from src.application.use_cases import (
    CompareEvaluationReportsInput,
    CompareEvaluationReportsUseCase,
    EvaluateAssistantInput,
    EvaluateAssistantUseCase,
)
from src.domain import (
    AssistantId,
    Document,
    DocumentId,
    DomainValidationError,
    EvaluationItem,
    SearchResult,
    first_relevant_rank,
    mean_reciprocal_rank,
    recall_at_k,
)
from src.infrastructure.evaluation import (
    EvaluationDatasetError,
    JsonEvaluationReportStore,
    JsonlEvaluationDatasetLoader,
    LLMAnswerJudge,
)


class InMemoryDocumentRepository:
    def __init__(self, documents: list[Document]) -> None:
        self.items = documents

    def save(self, document: Document) -> Document:
        self.items.append(document)
        return document

    def list_by_assistant(self, assistant_id: AssistantId) -> list[Document]:
        return [
            item for item in self.items if item.assistant_id == assistant_id
        ]


class RecordingLLM(ScriptedLLM):
    """Por padrao responde citando o primeiro trecho, como exige a RN-18."""

    def __init__(self, answer: str = "Resposta gerada [1].") -> None:
        super().__init__(answer)


class ScriptedJudge:
    def __init__(self, verdicts: list[bool]) -> None:
        self._verdicts = list(verdicts)
        self.calls = 0

    def is_faithful(
        self,
        *,
        question: str,
        answer: str,
        context_chunks: list[str],
    ) -> bool:
        self.calls += 1
        return self._verdicts.pop(0)


def _document(document_id: str, source_name: str) -> Document:
    return Document(
        id=DocumentId(document_id),
        assistant_id=AssistantId("assistant-1"),
        source_name=source_name,
        content_hash="hash",
    )


def _hit(document_id: str, text: str = "trecho", score: float = 0.9) -> SearchResult:
    return hit(document_id, text, score=score)


def _in_scope(item_id: str, source: str) -> EvaluationItem:
    return EvaluationItem(
        id=item_id,
        question=f"Pergunta {item_id}?",
        expected_answer="Resposta esperada.",
        source_documents=(source,),
        validated_by="curador",
    )


def _out_of_scope(item_id: str) -> EvaluationItem:
    return EvaluationItem(
        id=item_id,
        question=f"Pergunta fora de escopo {item_id}?",
        out_of_scope=True,
        validated_by="curador",
    )


class RetrievalMetricsTests(unittest.TestCase):
    """CT-01 (RF-25): recall@k e MRR com resultados conhecidos."""

    def test_first_relevant_rank_is_one_based(self) -> None:
        rank = first_relevant_rank(["a.md", "b.md", "c.md"], {"b.md"})
        self.assertEqual(rank, 2)

    def test_first_relevant_rank_is_none_when_absent(self) -> None:
        self.assertIsNone(first_relevant_rank(["a.md"], {"z.md"}))

    def test_recall_at_k_counts_ranks_within_k(self) -> None:
        self.assertEqual(recall_at_k([1, 5, 6, None], k=5), 0.5)

    def test_mean_reciprocal_rank(self) -> None:
        self.assertAlmostEqual(mean_reciprocal_rank([1, 2, None, 4]), 0.4375)

    def test_metrics_of_empty_set_are_zero(self) -> None:
        self.assertEqual(recall_at_k([], k=5), 0.0)
        self.assertEqual(mean_reciprocal_rank([]), 0.0)

    def test_recall_rejects_non_positive_k(self) -> None:
        with self.assertRaises(ValueError):
            recall_at_k([1], k=0)


class EvaluationItemTests(unittest.TestCase):
    """CT-02 (RF-24, RN-15): invariantes do item de referencia."""

    def test_in_scope_item_requires_source_document(self) -> None:
        with self.assertRaises(DomainValidationError):
            EvaluationItem(
                id="q1",
                question="Qual o prazo?",
                expected_answer="Dez dias.",
            )

    def test_in_scope_item_requires_expected_answer(self) -> None:
        with self.assertRaises(DomainValidationError):
            EvaluationItem(
                id="q1",
                question="Qual o prazo?",
                source_documents=("manual.md",),
            )

    def test_question_must_not_be_empty(self) -> None:
        with self.assertRaises(DomainValidationError):
            EvaluationItem(id="q1", question="  ", out_of_scope=True)

    def test_out_of_scope_item_needs_no_source(self) -> None:
        item = EvaluationItem(id="q1", question="Tema alheio?", out_of_scope=True)
        self.assertTrue(item.out_of_scope)
        self.assertFalse(item.is_validated)

    def test_item_is_validated_when_curator_is_named(self) -> None:
        self.assertTrue(_in_scope("q1", "manual.md").is_validated)


class DatasetLoaderTests(unittest.TestCase):
    """CT-02 (RF-24, RN-15): conjunto invalido e rejeitado por inteiro."""

    def _write(self, lines: list[dict[str, object] | str]) -> Path:
        directory = Path(tempfile.mkdtemp())
        path = directory / "dataset.jsonl"
        rendered = [
            line if isinstance(line, str) else json.dumps(line)
            for line in lines
        ]
        path.write_text("\n".join(rendered) + "\n", encoding="utf-8")
        return path

    def _valid_line(self, item_id: str = "q1") -> dict[str, object]:
        return {
            "id": item_id,
            "question": "Qual o prazo de reembolso?",
            "expected_answer": "Ate 10 dias uteis.",
            "source_documents": ["manual.md"],
            "validated_by": "curador",
        }

    def test_loads_valid_items_and_skips_blank_lines(self) -> None:
        path = self._write([self._valid_line("q1"), "", self._valid_line("q2")])
        items = JsonlEvaluationDatasetLoader().load(path)
        self.assertEqual([item.id for item in items], ["q1", "q2"])
        self.assertEqual(items[0].source_documents, ("manual.md",))

    def test_rejects_item_without_source_document(self) -> None:
        line = self._valid_line()
        line["source_documents"] = []
        path = self._write([line])
        with self.assertRaises(EvaluationDatasetError) as raised:
            JsonlEvaluationDatasetLoader().load(path)
        self.assertEqual(len(raised.exception.errors), 1)
        self.assertIn("linha 1", raised.exception.errors[0])

    def test_reports_every_invalid_line(self) -> None:
        missing_source = self._valid_line("q2")
        del missing_source["source_documents"]
        path = self._write([self._valid_line("q1"), "{nao e json", missing_source])
        with self.assertRaises(EvaluationDatasetError) as raised:
            JsonlEvaluationDatasetLoader().load(path)
        self.assertEqual(len(raised.exception.errors), 2)

    def test_rejects_duplicated_ids(self) -> None:
        path = self._write([self._valid_line("q1"), self._valid_line("q1")])
        with self.assertRaises(EvaluationDatasetError):
            JsonlEvaluationDatasetLoader().load(path)

    def test_rejects_unvalidated_items_by_default(self) -> None:
        line = self._valid_line()
        line["validated_by"] = None
        path = self._write([line])
        with self.assertRaises(EvaluationDatasetError):
            JsonlEvaluationDatasetLoader().load(path)

    def test_accepts_unvalidated_items_when_allowed(self) -> None:
        line = self._valid_line()
        line["validated_by"] = None
        path = self._write([line])
        items = JsonlEvaluationDatasetLoader(allow_unvalidated=True).load(path)
        self.assertFalse(items[0].is_validated)

    def test_rejects_empty_dataset(self) -> None:
        path = self._write([""])
        with self.assertRaises(EvaluationDatasetError):
            JsonlEvaluationDatasetLoader().load(path)


class EvaluateAssistantUseCaseTests(unittest.TestCase):
    """RF-25: o caso de uso mede o pipeline pelas mesmas portas do chat."""

    def _use_case(
        self,
        *,
        results: list[list[SearchResult]],
        llm: RecordingLLM | None = None,
        judge: ScriptedJudge | None = None,
    ) -> tuple[EvaluateAssistantUseCase, ScriptedVectorStore]:
        vector_store = ScriptedVectorStore(results)
        use_case = EvaluateAssistantUseCase(
            document_repository=InMemoryDocumentRepository(
                [_document("d1", "manual.md"), _document("d2", "outro.md")]
            ),
            context_retriever=build_retriever(vector_store),
            token_counter=WordTokenCounter(),
            answer_generator=(
                GroundedAnswerGenerator(llm_gateway=llm) if llm else None
            ),
            answer_judge=judge,
        )
        return use_case, vector_store

    def test_computes_recall_and_mrr_from_source_names(self) -> None:
        use_case, vector_store = self._use_case(
            results=[
                [_hit("d1", score=0.9), _hit("d2", score=0.8)],
                [_hit("d2", score=0.9), _hit("d1", score=0.8)],
                [_hit("d2")],
            ]
        )
        report = use_case.execute(
            EvaluateAssistantInput(
                assistant_id="assistant-1",
                items=(
                    _in_scope("q1", "manual.md"),
                    _in_scope("q2", "manual.md"),
                    _in_scope("q3", "manual.md"),
                ),
            )
        )
        self.assertAlmostEqual(report.metrics["recall_at_k"], 2 / 3)
        self.assertAlmostEqual(report.metrics["mrr"], (1 + 0.5 + 0) / 3)
        self.assertEqual(
            vector_store.calls[0]["collection"], "assistant-assistant-1"
        )
        self.assertEqual(report.items[1]["first_relevant_rank"], 2)

    def test_search_requests_the_configured_number_of_candidates(self) -> None:
        use_case, vector_store = self._use_case(results=[[_hit("d1")]])
        use_case.execute(
            EvaluateAssistantInput(
                assistant_id="assistant-1",
                items=(_in_scope("q1", "manual.md"),),
                k=5,
            )
        )
        self.assertEqual(vector_store.calls[0]["limit"], 30)

    def test_recall_is_measured_after_the_reranking(self) -> None:
        """A ordem que conta e a do reranker, nao a da busca."""
        use_case, _ = self._use_case(
            results=[[_hit("d2", score=0.2), _hit("d1", score=0.95)]]
        )
        report = use_case.execute(
            EvaluateAssistantInput(
                assistant_id="assistant-1",
                items=(_in_scope("q1", "manual.md"),),
            )
        )
        self.assertEqual(report.items[0]["first_relevant_rank"], 1)

    def test_generation_uses_only_the_top_n_chunks(self) -> None:
        llm = RecordingLLM()
        hits = [_hit("d2", f"trecho {index}") for index in range(7)]
        use_case, _ = self._use_case(results=[hits], llm=llm)
        use_case.execute(
            EvaluateAssistantInput(
                assistant_id="assistant-1",
                items=(_in_scope("q1", "manual.md"),),
                k=7,
            )
        )
        self.assertEqual(len(llm.calls[0]["context_chunks"]), 5)

    def test_candidates_below_the_minimum_score_count_as_fallback(self) -> None:
        """CT-14 na avaliacao: sem trecho relevante o LLM nao e chamado."""
        llm = RecordingLLM()
        use_case, _ = self._use_case(
            results=[[_hit("d1", score=0.49)]],
            llm=llm,
        )
        report = use_case.execute(
            EvaluateAssistantInput(
                assistant_id="assistant-1",
                items=(_out_of_scope("o1"),),
            )
        )
        self.assertEqual(report.metrics["fallback_accuracy"], 1.0)
        self.assertEqual(llm.calls, [])

    def test_answer_without_valid_citation_counts_as_fallback(self) -> None:
        use_case, _ = self._use_case(
            results=[[_hit("d1")]],
            llm=RecordingLLM(answer="Resposta sem fonte [9]."),
        )
        report = use_case.execute(
            EvaluateAssistantInput(
                assistant_id="assistant-1",
                items=(_out_of_scope("o1"),),
            )
        )
        self.assertEqual(report.metrics["fallback_accuracy"], 1.0)

    def test_out_of_scope_without_context_counts_as_correct_fallback(self) -> None:
        llm = RecordingLLM()
        use_case, _ = self._use_case(results=[[], [_hit("d1")]], llm=llm)
        report = use_case.execute(
            EvaluateAssistantInput(
                assistant_id="assistant-1",
                items=(_out_of_scope("o1"), _out_of_scope("o2")),
            )
        )
        self.assertEqual(report.metrics["fallback_accuracy"], 0.5)
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(report.metrics["recall_at_k"], 0.0)

    def test_empty_llm_answer_counts_as_fallback(self) -> None:
        use_case, _ = self._use_case(
            results=[[_hit("d1")]],
            llm=RecordingLLM(answer="   "),
        )
        report = use_case.execute(
            EvaluateAssistantInput(
                assistant_id="assistant-1",
                items=(_out_of_scope("o1"),),
            )
        )
        self.assertEqual(report.metrics["fallback_accuracy"], 1.0)

    def test_faithfulness_is_judged_only_for_answered_in_scope_items(self) -> None:
        judge = ScriptedJudge([True, False])
        use_case, _ = self._use_case(
            results=[[_hit("d1")], [_hit("d1")], [], [_hit("d1")]],
            llm=RecordingLLM(),
            judge=judge,
        )
        report = use_case.execute(
            EvaluateAssistantInput(
                assistant_id="assistant-1",
                items=(
                    _in_scope("q1", "manual.md"),
                    _in_scope("q2", "manual.md"),
                    _in_scope("q3", "manual.md"),
                    _out_of_scope("o1"),
                ),
            )
        )
        self.assertEqual(judge.calls, 2)
        self.assertEqual(report.metrics["faithfulness"], 0.5)

    def test_retrieval_only_run_leaves_generation_metrics_empty(self) -> None:
        use_case, _ = self._use_case(results=[[_hit("d1")], [_hit("d1")]])
        report = use_case.execute(
            EvaluateAssistantInput(
                assistant_id="assistant-1",
                items=(_in_scope("q1", "manual.md"), _out_of_scope("o1")),
            )
        )
        self.assertIsNone(report.metrics["faithfulness"])
        self.assertIsNone(report.metrics["fallback_accuracy"])
        self.assertEqual(report.metrics["recall_at_k"], 1.0)

    def test_report_carries_parameters_and_validation_flag(self) -> None:
        use_case, _ = self._use_case(results=[[_hit("d1")]])
        unvalidated = EvaluationItem(
            id="q1",
            question="Qual o prazo?",
            expected_answer="Dez dias.",
            source_documents=("manual.md",),
        )
        report = use_case.execute(
            EvaluateAssistantInput(
                assistant_id="assistant-1",
                items=(unvalidated,),
                parameters={"commit": "abc123"},
            )
        )
        self.assertFalse(report.validated)
        self.assertEqual(report.parameters["commit"], "abc123")
        self.assertEqual(report.to_dict()["k"], 5)

    def test_rejects_empty_item_list(self) -> None:
        use_case, _ = self._use_case(results=[])
        with self.assertRaises(ValueError):
            use_case.execute(
                EvaluateAssistantInput(assistant_id="assistant-1", items=())
            )


class CompareEvaluationReportsTests(unittest.TestCase):
    """CT-03 (RF-26, RN-14): regressao acima da tolerancia."""

    def _compare(
        self,
        current: dict[str, float | None],
        previous: dict[str, float | None] | None,
        tolerance: float = 0.02,
    ):
        return CompareEvaluationReportsUseCase().execute(
            CompareEvaluationReportsInput(
                current=current,
                previous=previous,
                tolerance=tolerance,
            )
        )

    def test_flags_metric_that_dropped_beyond_tolerance(self) -> None:
        result = self._compare(
            {"recall_at_k": 0.70, "mrr": 0.60},
            {"recall_at_k": 0.80, "mrr": 0.60},
        )
        self.assertTrue(result.has_regression)
        self.assertEqual(result.regressions, ("recall_at_k",))
        self.assertAlmostEqual(result.deltas["recall_at_k"], -0.10)

    def test_drop_within_tolerance_is_not_a_regression(self) -> None:
        result = self._compare({"recall_at_k": 0.79}, {"recall_at_k": 0.80})
        self.assertFalse(result.has_regression)

    def test_drop_equal_to_tolerance_is_not_a_regression(self) -> None:
        result = self._compare({"recall_at_k": 0.78}, {"recall_at_k": 0.80})
        self.assertFalse(result.has_regression)

    def test_improvement_is_reported_as_positive_delta(self) -> None:
        result = self._compare({"recall_at_k": 0.90}, {"recall_at_k": 0.80})
        self.assertFalse(result.has_regression)
        self.assertAlmostEqual(result.deltas["recall_at_k"], 0.10)

    def test_metrics_missing_on_either_side_are_ignored(self) -> None:
        result = self._compare(
            {"recall_at_k": 0.80, "faithfulness": None},
            {"recall_at_k": 0.80, "faithfulness": 0.95},
        )
        self.assertFalse(result.has_regression)
        self.assertNotIn("faithfulness", result.deltas)

    def test_first_run_has_no_baseline(self) -> None:
        result = self._compare({"recall_at_k": 0.80}, None)
        self.assertFalse(result.has_regression)
        self.assertEqual(result.deltas, {})

    def test_rejects_negative_tolerance(self) -> None:
        with self.assertRaises(ValueError):
            self._compare({"recall_at_k": 0.8}, {"recall_at_k": 0.8}, -0.1)


class LLMAnswerJudgeTests(unittest.TestCase):
    def test_answer_starting_with_sim_is_faithful(self) -> None:
        judge = LLMAnswerJudge(llm_gateway=RecordingLLM(answer="SIM. Sustentada."))
        self.assertTrue(
            judge.is_faithful(question="q", answer="a", context_chunks=["c"])
        )

    def test_any_other_verdict_is_not_faithful(self) -> None:
        for verdict in ("NAO", "Não.", "", "talvez sim"):
            judge = LLMAnswerJudge(llm_gateway=RecordingLLM(answer=verdict))
            self.assertFalse(
                judge.is_faithful(question="q", answer="a", context_chunks=["c"])
            )

    def test_answer_without_context_is_never_faithful(self) -> None:
        llm = RecordingLLM(answer="SIM")
        judge = LLMAnswerJudge(llm_gateway=llm)
        self.assertFalse(
            judge.is_faithful(question="q", answer="a", context_chunks=[])
        )
        self.assertEqual(llm.calls, [])


class ReportStoreTests(unittest.TestCase):
    """RF-26: relatorio gravado e relatorio anterior recuperado."""

    def _report(self, recall: float) -> dict[str, object]:
        return {
            "assistant_id": "assistant-1",
            "created_at": "2026-10-07T12:00:00+00:00",
            "k": 5,
            "validated": True,
            "metrics": {
                "recall_at_k": recall,
                "mrr": 0.5,
                "faithfulness": None,
                "fallback_accuracy": None,
            },
            "parameters": {"commit": "abc123"},
            "items": [],
        }

    def test_first_run_has_no_previous_report(self) -> None:
        store = JsonEvaluationReportStore(Path(tempfile.mkdtemp()))
        self.assertIsNone(store.load_latest("piloto"))

    def test_saves_json_and_markdown_and_reads_latest(self) -> None:
        store = JsonEvaluationReportStore(Path(tempfile.mkdtemp()))
        first = store.save("piloto", self._report(0.4), label="20261007-120000-aaa")
        store.save("piloto", self._report(0.8), label="20261008-120000-bbb")
        self.assertTrue(first.exists())
        self.assertTrue(first.with_suffix(".md").exists())
        latest = store.load_latest("piloto")
        self.assertIsNotNone(latest)
        self.assertEqual(latest["metrics"]["recall_at_k"], 0.8)

    def test_markdown_summary_lists_metrics_and_deltas(self) -> None:
        store = JsonEvaluationReportStore(Path(tempfile.mkdtemp()))
        path = store.save(
            "piloto",
            self._report(0.8),
            label="20261008-120000-bbb",
            deltas={"recall_at_k": 0.4},
            regressions=(),
        )
        summary = path.with_suffix(".md").read_text(encoding="utf-8")
        self.assertIn("recall_at_k", summary)
        self.assertIn("+0.400", summary)
        self.assertIn("abc123", summary)


if __name__ == "__main__":
    unittest.main()
