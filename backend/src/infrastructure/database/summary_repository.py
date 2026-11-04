"""SPEC-018: resumo do documento pessoal no PostgreSQL (D30, D36)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from src.domain import (
    Citation,
    DocumentId,
    DocumentSummary,
    DocumentSummarySection,
    SummaryStage,
)

from .models import DocumentSummaryModel, DocumentSummarySectionModel
from .repositories import _citations_from_json, _citations_to_json
from .transactions import commit_or_rollback


def _now() -> datetime:
    return datetime.now(UTC)


class PostgresDocumentSummaryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, summary: DocumentSummary) -> DocumentSummary:
        self._session.add(
            DocumentSummaryModel(
                document_id=summary.document_id.value,
                stage=summary.stage.value,
                batches_done=summary.batches_done,
                batches_total=summary.batches_total,
                content=summary.content,
                citations=_citations_to_json(summary.citations),
                document_tokens=summary.document_tokens,
                prompt_version=summary.prompt_version,
                model=summary.model,
                failure_code=summary.failure_code,
                created_at=summary.created_at,
                updated_at=summary.updated_at,
            )
        )
        commit_or_rollback(self._session)
        return summary

    def get(self, document_id: DocumentId) -> DocumentSummary | None:
        model = self._session.get(DocumentSummaryModel, document_id.value)
        if model is None:
            return None
        # O worker grava em outra sessao: le o estado atual do banco.
        self._session.refresh(model)
        return _summary_to_entity(model)

    def set_stage(
        self,
        document_id: DocumentId,
        stage: SummaryStage,
        *,
        batches_done: int = 0,
        batches_total: int = 0,
        document_tokens: int | None = None,
    ) -> None:
        values: dict[str, object] = {
            "stage": stage.value,
            "batches_done": batches_done,
            "batches_total": batches_total,
            "failure_code": None,
            "updated_at": _now(),
        }
        if document_tokens is not None:
            values["document_tokens"] = document_tokens
        self._update(document_id, values)

    def save_section(self, section: DocumentSummarySection) -> None:
        model = self._session.get(
            DocumentSummarySectionModel, (section.document_id.value, section.position)
        )
        if model is None:
            model = DocumentSummarySectionModel(
                document_id=section.document_id.value, position=section.position
            )
            self._session.add(model)
        model.title = section.title
        model.page_start = section.page_start
        model.input_tokens = section.input_tokens
        model.content = section.content
        commit_or_rollback(self._session)

    def list_sections(self, document_id: DocumentId) -> list[DocumentSummarySection]:
        rows = self._session.scalars(
            select(DocumentSummarySectionModel)
            .where(DocumentSummarySectionModel.document_id == document_id.value)
            .order_by(DocumentSummarySectionModel.position)
        ).all()
        return [
            DocumentSummarySection(
                document_id=DocumentId(row.document_id),
                position=row.position,
                title=row.title,
                input_tokens=row.input_tokens,
                content=row.content,
                page_start=row.page_start,
            )
            for row in rows
        ]

    def complete(
        self,
        document_id: DocumentId,
        *,
        content: str,
        citations: tuple[Citation, ...],
        prompt_version: str,
        model: str,
    ) -> None:
        self._update(
            document_id,
            {
                "stage": SummaryStage.READY.value,
                "content": content,
                "citations": _citations_to_json(citations),
                "prompt_version": prompt_version,
                "model": model,
                "failure_code": None,
                "updated_at": _now(),
            },
        )

    def fail(self, document_id: DocumentId, failure_code: str) -> None:
        self._update(
            document_id,
            {
                "stage": SummaryStage.FAILED.value,
                "failure_code": failure_code,
                "updated_at": _now(),
            },
        )

    def delete_content(self, document_id: DocumentId) -> None:
        """D10: sai o texto dos mini-resumos e do consolidado; fica a linha."""
        self._session.execute(
            delete(DocumentSummarySectionModel).where(
                DocumentSummarySectionModel.document_id == document_id.value
            )
        )
        self._session.execute(
            update(DocumentSummaryModel)
            .where(DocumentSummaryModel.document_id == document_id.value)
            .values(
                stage=SummaryStage.EXPIRED.value,
                content=None,
                citations=None,
                updated_at=_now(),
            )
        )
        commit_or_rollback(self._session)

    def _update(self, document_id: DocumentId, values: dict[str, object]) -> None:
        self._session.execute(
            update(DocumentSummaryModel)
            .where(DocumentSummaryModel.document_id == document_id.value)
            .values(**values)
        )
        commit_or_rollback(self._session)


def _summary_to_entity(model: DocumentSummaryModel) -> DocumentSummary:
    return DocumentSummary(
        document_id=DocumentId(model.document_id),
        stage=SummaryStage(model.stage),
        batches_done=model.batches_done,
        batches_total=model.batches_total,
        content=model.content,
        citations=_citations_from_json(model.citations),
        document_tokens=model.document_tokens,
        prompt_version=model.prompt_version,
        model=model.model,
        failure_code=model.failure_code,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
