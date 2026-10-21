from __future__ import annotations

import logging
import time
from collections.abc import Callable
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
    ChatMessage,
    ContextChunk,
    ConversationId,
    DocumentRepository,
    EvaluationItem,
    EvaluationItemResult,
    EvaluationMetrics,
    EvaluationReport,
    MessageId,
    MessageRole,
    SearchResult,
    TokenCounter,
    first_relevant_rank,
    mean_reciprocal_rank,
    recall_at_k,
)


logger = logging.getLogger(__name__)

# Decisao do autor (2026-10-21, V6 da rc6): uma falha do LLM num item (por exemplo, tempo
# esgotado) repete o item uma vez, depois desta espera; a segunda falha interrompe a
# avaliacao. So na avaliacao: o chat segue a D2 da SPEC-009.
ITEM_RETRY_DELAY_SECONDS = 5.0


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
        item_retry_delay_seconds: float = ITEM_RETRY_DELAY_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._item_retry_delay = item_retry_delay_seconds
        self._sleep = sleep
        self._retried: list[str] = []
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
        self._retried = []
        results = tuple(
            self._evaluate_with_retry(item, assistant_id, source_names, data)
            for item in data.items
        )
        parameters = dict(data.parameters)
        parameters["item_retries"] = ", ".join(self._retried) or "nenhum"
        report = EvaluationReport(
            assistant_id=assistant_id,
            k=data.k,
            metrics=_summarize(results, data.k),
            item_results=results,
            validated=all(item.is_validated for item in data.items),
            parameters=parameters,
        )
        return EvaluationReportDTO.from_report(report)

    def _evaluate_with_retry(
        self,
        item: EvaluationItem,
        assistant_id: AssistantId,
        source_names: dict[str, str],
        data: EvaluateAssistantInput,
    ) -> EvaluationItemResult:
        """Falha do provedor de LLM (RuntimeError) num item: repete uma vez."""
        try:
            return self._evaluate_item(item, assistant_id, source_names, data)
        except RuntimeError as exc:
            logger.warning(
                "evaluation.item.retrying",
                extra={
                    "item_id": item.id,
                    "error_type": type(exc).__name__,
                    "delay_seconds": self._item_retry_delay,
                },
            )
            self._retried.append(item.id)
            self._sleep(self._item_retry_delay)
            return self._evaluate_item(item, assistant_id, source_names, data)

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
        ranked = self._retrieve(self._search_query(item), assistant_id, data)
        sources = tuple(
            source_names.get(hit.document_id.value, "")
            for hit in ranked[: data.k]
        )
        context = fit_context(
            self._retriever.select_relevant(ranked),
            self._token_counter,
            self._retriever.settings.context_token_budget,
        )
        answer, fallback_used = self._answer(item, context)
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
            cited=self._cited(item, answer, fallback_used),
        )

    def _search_query(self, item: EvaluationItem) -> str:
        """RF-36: pergunta de continuacao e reescrita com o historico do item.

        Sem gerador (``--no-generation``) nao ha LLM para reescrever e a
        pergunta segue como foi escrita.
        """
        if not item.history or self._answer_generator is None:
            return item.question
        return self._answer_generator.rewrite_question(
            item.question, _history_messages(item)
        )

    @staticmethod
    def _cited(
        item: EvaluationItem,
        answer: str | None,
        fallback_used: bool | None,
    ) -> bool | None:
        if fallback_used is None or item.out_of_scope:
            return None
        return answer is not None

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
        item: EvaluationItem,
        context: list[ContextChunk],
    ) -> tuple[str | None, bool | None]:
        """Reproduz a decisao de fallback do grafo do chat, sem persistir nada."""
        if self._answer_generator is None:
            return None, None
        grounded = self._answer_generator.answer(
            question=item.question,
            context_chunks=context,
            history=_history_messages(item),
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


def _history_messages(item: EvaluationItem) -> list[ChatMessage]:
    return [
        ChatMessage(
            id=MessageId(f"{item.id}-h{index}"),
            conversation_id=ConversationId(f"eval-{item.id}"),
            role=MessageRole(role),
            content=content,
        )
        for index, (role, content) in enumerate(item.history, start=1)
    ]


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
        citation_coverage=_ratio(
            [item.cited for item in results if item.cited is not None]
        ),
    )


def _ratio(flags: list[bool]) -> float | None:
    if not flags:
        return None
    return sum(1 for flag in flags if flag) / len(flags)
