"""SPEC-018 (RN-61, T3): roteamento da mensagem na conversa do resumidor.

As rotas de finalidade, progresso e resumo gravado respondem sem LLM e sem
passar pelo grafo do chat; o resumo sob medida faz uma chamada sobre os
mini-resumos; a pergunta pontual segue o grafo com o escopo pessoal.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain import (
    Citation,
    ConversationId,
    Document,
    DocumentRepository,
    DocumentSummary,
    DocumentSummaryRepository,
    DocumentSummarySection,
    PersonalScope,
    SummarizerCapabilities,
    SummarizerRoute,
    SummaryProgress,
    SummaryStage,
    capabilities_markdown,
    progress_markdown,
    route_summarizer_message,
    summary_progress,
)


@dataclass(frozen=True, slots=True)
class SummarizerPlan:
    route: SummarizerRoute
    document: Document | None = None
    summary: DocumentSummary | None = None
    progress: SummaryProgress | None = None

    @property
    def answers_directly(self) -> bool:
        """Tudo menos a pergunta pontual fica fora do grafo do chat."""
        return self.route is not SummarizerRoute.QUESTION

    @property
    def counts_as_question(self) -> bool:
        """RN-65: so o que chama o LLM conta nos limites de perguntas."""
        return self.route in (SummarizerRoute.QUESTION, SummarizerRoute.TAILORED_SUMMARY)

    @property
    def personal_scope(self) -> PersonalScope | None:
        return self.document.personal_scope if self.document else None


class SummarizerChat:
    def __init__(
        self,
        *,
        documents: DocumentRepository,
        summaries: DocumentSummaryRepository,
        capabilities: SummarizerCapabilities,
    ) -> None:
        self._documents = documents
        self._summaries = summaries
        self._capabilities = capabilities

    def plan(self, conversation_id: ConversationId, question: str) -> SummarizerPlan:
        document = self._documents.get_personal_by_conversation(conversation_id)
        if document is None:
            return SummarizerPlan(route=route_summarizer_message(question, None))
        summary = self._summaries.get(document.id)
        progress = summary_progress(document, summary)
        return SummarizerPlan(
            route=route_summarizer_message(question, progress),
            document=document,
            summary=summary,
            progress=progress,
        )

    def direct_answer(self, plan: SummarizerPlan) -> tuple[str, tuple[Citation, ...]]:
        """Rotas 1 a 3 da RN-61, sem LLM (RNF-37, RNF-38)."""
        if plan.route is SummarizerRoute.CAPABILITIES:
            expired = plan.progress is not None and plan.progress.stage is SummaryStage.EXPIRED
            reason = "expired" if expired else "no_document"
            return capabilities_markdown(self._capabilities, reason=reason), ()
        if plan.route is SummarizerRoute.STORED_SUMMARY and plan.summary is not None:
            return plan.summary.content or "", plan.summary.citations
        if plan.route is SummarizerRoute.PROGRESS and plan.document and plan.progress:
            return progress_markdown(plan.progress, plan.document.source_name), ()
        raise ValueError(f"route {plan.route} has no direct answer.")

    def sections(self, plan: SummarizerPlan) -> list[DocumentSummarySection]:
        if plan.document is None:
            return []
        return self._summaries.list_sections(plan.document.id)
