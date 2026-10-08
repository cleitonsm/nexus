"""Dubles da fila de processamento e do relogio (SPEC-005)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.domain import (
    Document,
    DocumentStatus,
    IngestionJob,
    IngestionJobStatus,
)



class ManualClock:
    """Relogio real deslocado: jobs criados nos testes ja estao disponiveis."""

    def __init__(self) -> None:
        self.offset = timedelta(0)

    def __call__(self) -> datetime:
        return datetime.now(UTC) + self.offset

    def advance(self, seconds: float) -> None:
        self.offset += timedelta(seconds=seconds)


class InMemoryIngestionJobQueue:
    """Fila em memoria com as mesmas regras da fila em PostgreSQL.

    ``documents`` e ``reindex_jobs`` sao os dubles dos repositorios: a fila
    grava o documento junto com o job, como a implementacao real faz numa
    unica transacao, e nao reserva jobs de assistente em reindexacao (D8).
    """

    def __init__(self, documents, reindex_jobs=None) -> None:
        self.documents = documents
        self.reindex_jobs = reindex_jobs
        self.jobs: dict[str, IngestionJob] = {}
        self.fail_next_enqueue = False

    def enqueue(self, job: IngestionJob) -> IngestionJob:
        if self.fail_next_enqueue:
            self.fail_next_enqueue = False
            raise RuntimeError("queue unavailable")
        self.jobs[job.id] = job
        return job

    def reserve_next(self, now: datetime) -> IngestionJob | None:
        available = sorted(
            (
                job
                for job in self.jobs.values()
                if job.status is IngestionJobStatus.PENDING
                and job.available_at <= now
                and self._document_exists(job)
                and not self._reindexing(job)
            ),
            key=lambda job: (job.available_at, job.created_at),
        )
        if not available:
            return None
        reserved = available[0].reserve(now)
        self.jobs[reserved.id] = reserved
        return reserved

    def list_expired(self, reserved_before: datetime) -> list[IngestionJob]:
        return [
            job
            for job in self.jobs.values()
            if job.status is IngestionJobStatus.PROCESSING
            and job.reserved_at is not None
            and job.reserved_at < reserved_before
        ]

    def complete(
        self,
        job: IngestionJob,
        document: Document,
        replaced: Document | None = None,
    ) -> None:
        self.jobs[job.id] = job
        self.documents.save(document)
        if replaced is not None:
            self.documents.save(replaced)

    def retry(self, job: IngestionJob, document: Document) -> None:
        self.jobs[job.id] = job
        self.documents.save(document)

    def fail(self, job: IngestionJob, document: Document) -> None:
        self.jobs[job.id] = job
        self.documents.save(document)

    def pending(self) -> list[IngestionJob]:
        return [
            job for job in self.jobs.values() if job.status is IngestionJobStatus.PENDING
        ]

    def drop_jobs_of_deleted_documents(self) -> None:
        """Como o ``ON DELETE CASCADE`` da tabela real."""
        self.jobs = {
            key: job for key, job in self.jobs.items() if self._document_exists(job)
        }

    def _document_exists(self, job: IngestionJob) -> bool:
        return self.documents.get_by_id(job.document_id) is not None

    def _reindexing(self, job: IngestionJob) -> bool:
        if self.reindex_jobs is None:
            return False
        document = self.documents.get_by_id(job.document_id)
        return self.reindex_jobs.get_running(document.assistant_id) is not None


def current_documents(items: dict[str, Document], assistant_id) -> list[Document]:
    """``list_by_assistant`` real: versoes substituidas ficam de fora."""
    return [
        item
        for item in items.values()
        if item.assistant_id == assistant_id
        and item.status is not DocumentStatus.REPLACED
    ]


def find_current_by_hash(
    items: dict[str, Document],
    assistant_id,
    content_hash: str,
) -> Document | None:
    return next(
        (
            item
            for item in current_documents(items, assistant_id)
            if item.content_hash == content_hash
        ),
        None,
    )

