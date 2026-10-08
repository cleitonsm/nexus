from __future__ import annotations

from dataclasses import dataclass, field

from src.application.dto import EvaluationReportDTO
from src.application.services import (
    ContextRetriever,
    GroundedAnswerGenerator,
    fit_context,
)
from src.domain import (
    AnswerJudge,
    AssistantId,
    ContextChunk,
    DocumentRepository,
    EvaluationItem,
    EvaluationItemResult,
    EvaluationMetrics,
    EvaluationReport,
    SearchResult,
    TokenCounter,
    first_relevant_rank,
    mean_reciprocal_rank,
    recall_at_k,
)


@dataclass(frozen=True, slots=True)
class EvaluateAssistantInput:
    assistant_id: str
    items: tuple[EvaluationItem, ...]
    k: int = 5
    parameters: dict[str, str] = field(default_factory=dict)


class EvaluateAssistantUseCase:
    """Mede recuperacao e resposta com os mesmos servicos usados pelo chat.

    A recuperacao e medida sobre os ``k`` primeiros apos o reranking. Sem
    `answer_generator` a execucao mede apenas a recuperacao; sem
    `answer_judge` a fidelidade nao e calculada.
    """

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        context_retriever: ContextRetriever,
        token_counter: TokenCounter,
        answer_generator: GroundedAnswerGenerator | None = None,
        answer_judge: AnswerJudge | None = None,
    ) -> None:
        self._document_repository = document_repository
        self._retriever = context_retriever
        self._token_counter = token_counter
        self._answer_generator = answer_generator
        self._answer_judge = answer_judge

    def execute(self, data: EvaluateAssistantInput) -> EvaluationReportDTO:
        if not data.items:
            raise ValueError("evaluation requires at least one item.")
        if data.k <= 0:
            raise ValueError("k must be positive.")

        assistant_id = AssistantId(data.assistant_id)
        source_names = self._source_names(assistant_id)
        results = tuple(
            self._evaluate_item(item, assistant_id, source_names, data)
            for item in data.items
        )
        report = EvaluationReport(
            assistant_id=assistant_id,
            k=data.k,
            metrics=_summarize(results, data.k),
            item_results=results,
            validated=all(item.is_validated for item in data.items),
            parameters=dict(data.parameters),
        )
        return EvaluationReportDTO.from_report(report)

    def _source_names(self, assistant_id: AssistantId) -> dict[str, str]:
        documents = self._document_repository.list_by_assistant(assistant_id)
        return {item.id.value: item.source_name for item in documents}

    def _evaluate_item(
        self,
        item: EvaluationItem,
        assistant_id: AssistantId,
        source_names: dict[str, str],
        data: EvaluateAssistantInput,
    ) -> EvaluationItemResult:
        ranked = self._retrieve(item.question, assistant_id, data)
        sources = tuple(
            source_names.get(hit.document_id.value, "")
            for hit in ranked[: data.k]
        )
        context = fit_context(
            self._retriever.select_relevant(ranked),
            self._token_counter,
            self._retriever.settings.context_token_budget,
        )
        answer, fallback_used = self._answer(item.question, context)
        return EvaluationItemResult(
            item_id=item.id,
            out_of_scope=item.out_of_scope,
            retrieved_sources=sources,
            first_relevant_rank=(
                None
                if item.out_of_scope
                else first_relevant_rank(sources, item.source_documents)
            ),
            fallback_used=fallback_used,
            faithful=self._judge(item, answer, context),
        )

    def _retrieve(
        self,
        question: str,
        assistant_id: AssistantId,
        data: EvaluateAssistantInput,
    ) -> list[SearchResult]:
        # A avaliacao mede a base inteira e nao tem usuario: sem restricao
        # por documento.
        candidates = self._retriever.search(
            assistant_id,
            question,
            user_groups=None,
        )
        return self._retriever.rerank(
            question,
            candidates,
            limit=max(data.k, self._retriever.settings.top_n),
        )

    def _answer(
        self,
        question: str,
        context: list[ContextChunk],
    ) -> tuple[str | None, bool | None]:
        """Reproduz a decisao de fallback do grafo do chat, sem persistir nada."""
        if self._answer_generator is None:
            return None, None
        grounded = self._answer_generator.answer(
            question=question,
            context_chunks=context,
            history=[],
        )
        if grounded is None:
            return None, True
        return grounded.text, False

    def _judge(
        self,
        item: EvaluationItem,
        answer: str | None,
        context: list[ContextChunk],
    ) -> bool | None:
        if self._answer_judge is None or answer is None or item.out_of_scope:
            return None
        return self._answer_judge.is_faithful(
            question=item.question,
            answer=answer,
            context_chunks=[chunk.text for chunk in context],
        )


def _summarize(
    results: tuple[EvaluationItemResult, ...],
    k: int,
) -> EvaluationMetrics:
    ranks = [item.first_relevant_rank for item in results if not item.out_of_scope]
    judged = [item.faithful for item in results if item.faithful is not None]
    fallbacks = [
        item.fallback_used
        for item in results
        if item.out_of_scope and item.fallback_used is not None
    ]
    return EvaluationMetrics(
        recall_at_k=recall_at_k(ranks, k),
        mrr=mean_reciprocal_rank(ranks),
        faithfulness=_ratio(judged),
        fallback_accuracy=_ratio(fallbacks),
    )


def _ratio(flags: list[bool]) -> float | None:
    if not flags:
        return None
    return sum(1 for flag in flags if flag) / len(flags)
