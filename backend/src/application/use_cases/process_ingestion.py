"""Processamento dos documentos em segundo plano (RF-48, RF-55, RNF-27).

Executado pelo worker, sem usuario: a autorizacao aconteceu no envio. Cada
passo pode ser repetido sem efeito colateral: os trechos tem identificador
deterministico e os do documento sao removidos antes de serem regravados.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.services import (
    MISSING_ORIGINAL_REASON,
    OUTDATED_INDEX_REASON,
    PIPELINE_VERSION,
    TIMEOUT_REASON,
    UNAVAILABLE_SERVICE_REASON,
    UNREADABLE_DOCUMENT_REASON,
    WORKER_USER,
    AccessControl,
    DocumentIndexer,
    IndexState,
    IngestionSettings,
    JobTimeoutError,
    is_index_outdated,
    read_index_state,
)
from src.domain import (
    AuditAction,
    AuditResource,
    CollectionName,
    Document,
    DocumentFileStorage,
    DocumentRepository,
    DocumentStatus,
    DomainValidationError,
    IndexOutdatedError,
    IngestionJob,
    IngestionJobQueue,
    ReindexInProgressError,
    ReindexJobRepository,
    VectorStoreGateway,
)

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class _DocumentGoneError(Exception):
    """O documento foi excluido enquanto era processado (C4)."""


@dataclass(frozen=True, slots=True)
class ProcessingOutcome:
    job_id: str
    document_id: str
    status: str
    attempts: int
    chunk_count: int = 0
    failure_reason: str | None = None


class _IngestionFailures:
    """Decide entre nova tentativa e falha definitiva (RN-30, C1, C2)."""

    def __init__(
        self,
        *,
        queue: IngestionJobQueue,
        vector_store: VectorStoreGateway,
        settings: IngestionSettings,
        access_control: AccessControl,
        clock: Callable[[], datetime],
    ) -> None:
        self._queue = queue
        self._vector_store = vector_store
        self._settings = settings
        self._access = access_control
        self._clock = clock

    def handle(
        self,
        job: IngestionJob,
        document: Document,
        error: Exception,
    ) -> ProcessingOutcome:
        detail = f"{type(error).__name__}: {error}"
        reason = _definitive_reason(error)
        if reason is None and job.attempts < self._settings.max_attempts:
            when = self._clock() + self._settings.delay_after(job.attempts)
            self._queue.retry(job.retry_at(when, detail), document.retry_later())
            logger.warning(
                "ingestion.job.retry",
                extra=_log_extra(job, document, error=detail),
            )
            return ProcessingOutcome(
                job_id=job.id,
                document_id=document.id.value,
                status=DocumentStatus.PENDING.value,
                attempts=job.attempts,
            )
        reason = reason or _exhausted_reason(error)
        self._discard_partial_chunks(document)
        failed = document.mark_failed(reason)
        self._queue.fail(job.fail(detail), failed)
        logger.error(
            "ingestion.job.failed",
            extra=_log_extra(job, document, error=detail),
        )
        self._access.audit(
            WORKER_USER,
            AuditAction.DOCUMENT_FAILED,
            resource_type=AuditResource.DOCUMENT,
            resource_id=document.id.value,
            details={
                "assistant_id": document.assistant_id.value,
                "source_name": document.source_name,
                "attempts": job.attempts,
                "reason": reason,
            },
        )
        return ProcessingOutcome(
            job_id=job.id,
            document_id=document.id.value,
            status=DocumentStatus.FAILED.value,
            attempts=job.attempts,
            failure_reason=reason,
        )

    def _discard_partial_chunks(self, document: Document) -> None:
        """Trechos inativos de uma tentativa interrompida nao devem sobrar."""
        try:
            self._vector_store.delete_by_document(
                CollectionName.from_assistant_id(document.assistant_id),
                document.id,
            )
        except Exception:  # noqa: BLE001 - a falha principal ja esta registrada
            logger.exception(
                "ingestion.job.cleanup_failed",
                extra={"document_id": document.id.value},
            )


def _definitive_reason(error: Exception) -> str | None:
    """Erros que se repetiriam em qualquer tentativa (C1)."""
    if isinstance(error, IndexOutdatedError):
        return OUTDATED_INDEX_REASON
    if isinstance(error, FileNotFoundError):
        return MISSING_ORIGINAL_REASON
    if isinstance(error, (ValueError, DomainValidationError)):
        return UNREADABLE_DOCUMENT_REASON
    return None


def _exhausted_reason(error: Exception) -> str:
    if isinstance(error, JobTimeoutError):
        return TIMEOUT_REASON
    return UNAVAILABLE_SERVICE_REASON


def _log_extra(
    job: IngestionJob,
    document: Document,
    **extra: object,
) -> dict[str, object]:
    return {
        "job_id": job.id,
        "document_id": document.id.value,
        "assistant_id": document.assistant_id.value,
        "attempt": job.attempts,
        **extra,
    }


class ProcessNextIngestionJobUseCase:
    """Reserva um job e leva o documento a ``indexado`` ou ``falhou``.

    Os trechos sao gravados inativos e so entram nas buscas ao final (RN-27);
    numa substituicao, a versao anterior responde ate esse momento e entao
    perde trechos e arquivo (RN-28, D5).
    """

    def __init__(
        self,
        *,
        job_queue: IngestionJobQueue,
        document_repository: DocumentRepository,
        vector_store_gateway: VectorStoreGateway,
        document_indexer: DocumentIndexer,
        file_storage: DocumentFileStorage,
        reindex_job_repository: ReindexJobRepository,
        access_control: AccessControl,
        settings: IngestionSettings | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._queue = job_queue
        self._documents = document_repository
        self._vector_store = vector_store_gateway
        self._indexer = document_indexer
        self._storage = file_storage
        self._reindex_jobs = reindex_job_repository
        self._access = access_control
        self._clock = clock
        self._failures = _IngestionFailures(
            queue=job_queue,
            vector_store=vector_store_gateway,
            settings=settings or IngestionSettings(),
            access_control=access_control,
            clock=clock,
        )

    def execute(self) -> ProcessingOutcome | None:
        """Processa um job; ``None`` quando nao ha job disponivel."""
        job = self._queue.reserve_next(self._clock())
        if job is None:
            return None
        document = self._documents.get_by_id(job.document_id)
        if document is None:
            # Excluido antes da reserva; o job saiu junto com o documento.
            return None
        document = self._documents.save(document.start_processing(job.attempts))
        logger.info("ingestion.job.started", extra=_log_extra(job, document))
        try:
            return self._index(job, document)
        except _DocumentGoneError:
            self._vector_store.delete_by_document(
                CollectionName.from_assistant_id(document.assistant_id),
                document.id,
            )
            logger.info("ingestion.job.document_gone", extra=_log_extra(job, document))
            return None
        except Exception as exc:  # noqa: BLE001 - toda falha vira estado
            return self._failures.handle(job, document, exc)

    def _index(self, job: IngestionJob, document: Document) -> ProcessingOutcome:
        collection = self._writable_collection(document)
        raw_content = self._storage.load(document.storage_key or "")
        chunks = self._indexer.build_chunks(
            assistant_id=document.assistant_id,
            document_id=document.id,
            source_name=document.source_name,
            content_type=None,
            raw_content=raw_content,
            allowed_groups=self._access.permissions.get_document_groups(document.id),
            active=False,
        )
        # Restos de uma tentativa interrompida (inclusive com mais trechos).
        self._vector_store.delete_by_document(collection, document.id)
        self._vector_store.upsert_chunks(collection_name=collection, chunks=chunks)

        previous = self._previous_version(document)
        self._ensure_still_wanted(document)
        self._vector_store.set_document_active(collection, document.id, True)
        if previous is not None:
            self._vector_store.delete_by_document(collection, previous.id)
        indexed = document.mark_indexed(
            embedding_model=self._indexer.embedding_model,
            pipeline_version=PIPELINE_VERSION,
            chunk_count=len(chunks),
        )
        self._queue.complete(
            job.complete(),
            indexed,
            previous.mark_replaced() if previous is not None else None,
        )
        if previous is not None and previous.storage_key:
            self._discard_original(previous)
        self._audit_indexed(job, indexed, previous)
        return ProcessingOutcome(
            job_id=job.id,
            document_id=indexed.id.value,
            status=indexed.status.value,
            attempts=job.attempts,
            chunk_count=indexed.chunk_count,
        )

    def _writable_collection(self, document: Document) -> CollectionName:
        """Alias do assistente; cria a primeira versao quando ainda nao existe.

        A reserva ja evita assistentes em reindexacao (D8); a verificacao aqui
        cobre a reindexacao iniciada entre a reserva e a gravacao.
        """
        assistant_id = document.assistant_id
        if self._reindex_jobs.get_running(assistant_id) is not None:
            raise ReindexInProgressError(
                "a reindex started for this assistant; retrying later."
            )
        state = read_index_state(self._vector_store, assistant_id)
        outdated = is_index_outdated(
            state,
            self._documents.list_by_assistant(assistant_id),
            embedding_model=self._indexer.embedding_model,
            pipeline_version=PIPELINE_VERSION,
        )
        if outdated:
            raise IndexOutdatedError("the assistant index is outdated.")
        return self._ensure_collection(state)

    def _ensure_collection(self, state: IndexState) -> CollectionName:
        if state.current is None:
            first = state.next_collection()
            self._vector_store.ensure_collection(
                collection_name=first,
                vector_size=self._indexer.embedding_dimension,
            )
            self._vector_store.point_alias(state.alias, first)
        return state.alias

    def _previous_version(self, document: Document) -> Document | None:
        if document.replaces_document_id is None:
            return None
        previous = self._documents.get_by_id(document.replaces_document_id)
        if previous is None or previous.status is not DocumentStatus.INDEXED:
            # A versao anterior foi excluida durante o processamento.
            return None
        return previous

    def _ensure_still_wanted(self, document: Document) -> None:
        """C4: exclusao durante o processamento vence o processamento."""
        if self._documents.get_by_id(document.id) is None:
            raise _DocumentGoneError(document.id.value)

    def _discard_original(self, previous: Document) -> None:
        try:
            self._storage.delete(previous.storage_key or "")
        except Exception:  # noqa: BLE001 - o arquivo orfao nao afeta as buscas
            logger.exception(
                "ingestion.previous_original.delete_failed",
                extra={"document_id": previous.id.value},
            )

    def _audit_indexed(
        self,
        job: IngestionJob,
        document: Document,
        previous: Document | None,
    ) -> None:
        details: dict[str, object] = {
            "assistant_id": document.assistant_id.value,
            "source_name": document.source_name,
            "chunk_count": document.chunk_count,
            "attempts": job.attempts,
            "version": document.version,
        }
        if previous is not None:
            details["replaced_document_id"] = previous.id.value
        self._access.audit(
            WORKER_USER,
            AuditAction.DOCUMENT_INDEXED,
            resource_type=AuditResource.DOCUMENT,
            resource_id=document.id.value,
            details=details,
        )
        logger.info(
            "ingestion.job.indexed",
            extra=_log_extra(job, document, chunk_count=document.chunk_count),
        )


class RequeueExpiredIngestionJobsUseCase:
    """Job reservado alem do limite volta a fila e conta como tentativa (D7)."""

    def __init__(
        self,
        *,
        job_queue: IngestionJobQueue,
        document_repository: DocumentRepository,
        vector_store_gateway: VectorStoreGateway,
        access_control: AccessControl,
        settings: IngestionSettings | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._queue = job_queue
        self._documents = document_repository
        self._settings = settings or IngestionSettings()
        self._clock = clock
        self._failures = _IngestionFailures(
            queue=job_queue,
            vector_store=vector_store_gateway,
            settings=self._settings,
            access_control=access_control,
            clock=clock,
        )

    def execute(self) -> list[ProcessingOutcome]:
        cutoff = self._clock() - self._settings.job_timeout
        outcomes: list[ProcessingOutcome] = []
        for job in self._queue.list_expired(cutoff):
            document = self._documents.get_by_id(job.document_id)
            if document is None or not document.is_in_progress:
                continue
            if document.status is not DocumentStatus.PROCESSING:
                # Parou entre a reserva e o inicio: retoma do estado pendente.
                document = document.start_processing(job.attempts)
            outcomes.append(
                self._failures.handle(
                    job,
                    document,
                    JobTimeoutError(
                        f"job reserved for more than "
                        f"{self._settings.job_timeout_seconds} seconds."
                    ),
                )
            )
        return outcomes
