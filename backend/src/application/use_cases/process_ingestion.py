"""Processamento dos documentos em segundo plano (RF-48, RF-55, RNF-27).

Executado pelo worker, sem usuario: a autorizacao aconteceu no envio. Cada
passo pode ser repetido sem efeito colateral: os trechos tem identificador
deterministico e os do documento sao removidos antes de serem regravados.
"""

from __future__ import annotations

import logging
from uuid import uuid4
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
    record_sparse_parameters,
)
from src.domain import (
    DOCUMENT_TOO_LONG,
    MAX_SUMMARY_DOCUMENT_TOKENS,
    PROCESSING_FAILED,
    SUMMARIZER_ASSISTANT_ID,
    SUMMARY_FAILED,
    DocumentSummaryRepository,
    DocumentTooLongError,
    IngestionJobKind,
    SummaryStage,
    TokenCounter,
    TransientServiceError,
    document_too_long_message,
    exceeds_summary_token_limit,
    AuditAction,
    AuditResource,
    CollectionName,
    Document,
    DocumentFileStorage,
    DocumentRepository,
    DocumentStatus,
    DomainValidationError,
    IndexOutdatedError,
    IndexParametersRepository,
    IngestionJob,
    IngestionJobQueue,
    JobOwnershipLostError,
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
    if isinstance(error, DocumentTooLongError):
        return str(error)  # SPEC-018 (D15): contagem e limite, em pt-BR
    if isinstance(error, IndexOutdatedError):
        return OUTDATED_INDEX_REASON
    if isinstance(error, FileNotFoundError):
        return MISSING_ORIGINAL_REASON
    if isinstance(error, TransientServiceError):
        return None  # fix-11: falha passageira, mesmo que seja ValueError
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
        index_parameters: IndexParametersRepository | None = None,
        summaries: DocumentSummaryRepository | None = None,
        token_counter: TokenCounter | None = None,
        summarizer: Callable[[IngestionJob, Document], ProcessingOutcome | None] | None = None,
    ) -> None:
        # SPEC-018: documento pessoal (contagem, escopo e etapas) e job de resumo.
        self._summaries = summaries
        self._token_counter = token_counter
        self._summarizer = summarizer
        self._queue = job_queue
        self._index_parameters = index_parameters
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
        if document.status is DocumentStatus.EXPIRED:
            # SPEC-018: documento pessoal apagado antes da reserva (lapide).
            self._queue.complete(job.complete(), document, None)
            return None
        if job.kind is IngestionJobKind.SUMMARIZE:
            # SPEC-018 (D21): o documento ja esta indexado; so o resumo roda.
            if self._summarizer is None:
                raise RuntimeError("summary job without a configured summarizer.")
            return self._summarizer(job, document)
        document = self._documents.save(document.start_processing(job.attempts))
        logger.info("ingestion.job.started", extra=_log_extra(job, document))
        try:
            return self._index(job, document)
        except _DocumentGoneError:
            self._vector_store.delete_by_document(
                CollectionName.from_assistant_id(document.assistant_id),
                document.id,
            )
            tombstone = self._documents.get_by_id(document.id)
            if tombstone is not None:
                # SPEC-018: a lapide fica; o job termina sem regravar o documento.
                self._queue.complete(job.complete(), tombstone, None)
            logger.info("ingestion.job.document_gone", extra=_log_extra(job, document))
            return None
        except JobOwnershipLostError:
            # Outra tentativa e dona do job: nao grava nada nem limpa trechos.
            logger.warning("ingestion.job.ownership_lost", extra=_log_extra(job, document))
            return None
        except Exception as exc:  # noqa: BLE001 - toda falha vira estado
            try:
                outcome = self._failures.handle(job, document, exc)
                self._fail_summary(document, outcome, exc)
                return outcome
            except JobOwnershipLostError:
                logger.warning(
                    "ingestion.job.ownership_lost", extra=_log_extra(job, document)
                )
                return None

    def _hold_reservation(self, job: IngestionJob) -> None:
        """Renova a reserva; sem ela, outro worker pode estar processando."""
        if not self._queue.renew(job, self._clock()):
            raise JobOwnershipLostError(job.id)

    def _fail_summary(
        self, document: Document, outcome: ProcessingOutcome, error: Exception
    ) -> None:
        """SPEC-018 (D36): o documento pessoal que falhou mostra o motivo."""
        if (
            self._summaries is None
            or not document.is_personal
            or outcome.status != DocumentStatus.FAILED.value
        ):
            return
        code = DOCUMENT_TOO_LONG if isinstance(error, DocumentTooLongError) else PROCESSING_FAILED
        self._summaries.fail(document.id, code)

    def _set_stage(self, document: Document, stage: SummaryStage, **values: int) -> None:
        if self._summaries is not None:
            self._summaries.set_stage(document.id, stage, **values)

    def _index_personal(self, job: IngestionJob, document: Document) -> ProcessingOutcome:
        """SPEC-018: conta antes de vetorizar (RN-60), grava com dono e conversa
        (RN-59) e enfileira o resumo depois da indexacao (D21)."""
        if self._token_counter is None:
            raise RuntimeError("personal documents need a token counter.")
        self._set_stage(document, SummaryStage.EXTRACTING)
        raw_content = self._storage.load(document.storage_key or "")
        extracted = self._indexer.extract(
            source_name=document.source_name, content_type=None, raw_content=raw_content
        )
        tokens = self._token_counter.count(extracted.plain_text)
        if exceeds_summary_token_limit(tokens):
            raise DocumentTooLongError(
                document_too_long_message(tokens),
                tokens=tokens,
                limit=MAX_SUMMARY_DOCUMENT_TOKENS,
            )
        self._set_stage(document, SummaryStage.INDEXING, document_tokens=tokens)
        collection = self._personal_collection()
        chunks = self._indexer.build_chunks(
            assistant_id=document.assistant_id,
            document_id=document.id,
            source_name=document.source_name,
            content_type=None,
            raw_content=raw_content,
            active=False,
            extracted=extracted,
            owner_user_id=document.owner_user_id,
            conversation_id=(
                document.conversation_id.value if document.conversation_id else None
            ),
        )
        self._hold_reservation(job)
        self._vector_store.delete_by_document(collection, document.id)
        self._vector_store.upsert_chunks(collection_name=collection, chunks=chunks)
        self._ensure_still_wanted(document)
        self._hold_reservation(job)
        self._vector_store.set_document_active(collection, document.id, True)
        indexed = document.mark_indexed(
            embedding_model=self._indexer.embedding_model,
            pipeline_version=PIPELINE_VERSION,
            chunk_count=len(chunks),
        )
        self._queue.complete(job.complete(), indexed, None)
        self._set_stage(indexed, SummaryStage.SUMMARIZING)
        self._queue.enqueue(
            IngestionJob(
                id=str(uuid4()), document_id=indexed.id, kind=IngestionJobKind.SUMMARIZE
            )
        )
        self._audit_indexed(job, indexed, None)
        return ProcessingOutcome(
            job_id=job.id,
            document_id=indexed.id.value,
            status=indexed.status.value,
            attempts=job.attempts,
            chunk_count=indexed.chunk_count,
        )

    def _personal_collection(self) -> CollectionName:
        """Collection do resumidor; com outro modelo de embedding, recria vazia.

        O resumidor nao e reindexado (RN-55): os documentos pessoais duram 30
        dias. Quem ja estava indexado perde so as perguntas pontuais; o resumo
        gravado continua.
        """
        state = read_index_state(self._vector_store, SUMMARIZER_ASSISTANT_ID)
        # Lapides acumulam: so os indexados (limitados pela retencao) contam.
        live = self._documents.list_personal_indexed()
        outdated = state.current is not None and is_index_outdated(
            state,
            live,
            embedding_model=self._indexer.embedding_model,
            pipeline_version=PIPELINE_VERSION,
        )
        if not outdated:
            return self._ensure_collection(state)
        stale = state.current
        fresh = state.next_collection()
        self._vector_store.ensure_collection(
            collection_name=fresh, vector_size=self._indexer.embedding_dimension
        )
        self._vector_store.point_alias(state.alias, fresh)
        record_sparse_parameters(self._index_parameters, fresh, self._indexer.sparse_parameters)
        if stale is not None:
            self._vector_store.delete_collection(stale)
        logger.warning(
            "summarizer.collection.recreated",
            extra={"stale": stale.value if stale else None, "fresh": fresh.value},
        )
        return state.alias

    def _index(self, job: IngestionJob, document: Document) -> ProcessingOutcome:
        if document.is_personal:
            return self._index_personal(job, document)
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
        self._hold_reservation(job)
        # Restos de uma tentativa interrompida (inclusive com mais trechos).
        self._vector_store.delete_by_document(collection, document.id)
        self._vector_store.upsert_chunks(collection_name=collection, chunks=chunks)

        previous = self._previous_version(document)
        self._ensure_still_wanted(document)
        self._hold_reservation(job)
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
            # PC-D2: parametros do BM25 com que a collection nasce.
            record_sparse_parameters(
                self._index_parameters, first, self._indexer.sparse_parameters
            )
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
        """C4: exclusao durante o processamento vence o processamento.

        SPEC-018: o documento pessoal apagado vira lapide ``expirado``.
        """
        current = self._documents.get_by_id(document.id)
        if current is None or current.status is DocumentStatus.EXPIRED:
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
        summaries: DocumentSummaryRepository | None = None,
    ) -> None:
        self._queue = job_queue
        self._documents = document_repository
        self._settings = settings or IngestionSettings()
        self._clock = clock
        self._summaries = summaries
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
            if (
                job.kind is IngestionJobKind.SUMMARIZE
                and document is not None
                and document.status is DocumentStatus.INDEXED
            ):
                self._requeue_summary(job, document)
                continue
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

    def _requeue_summary(self, job: IngestionJob, document: Document) -> None:
        """SPEC-018: o job de resumo vencido volta a fila ou derruba o resumo.

        Os mini-resumos ja gravados ficam: a nova tentativa continua dali.
        """
        detail = (
            f"JobTimeoutError: summary job reserved for more than "
            f"{self._settings.job_timeout_seconds} seconds."
        )
        if job.attempts < self._settings.max_attempts:
            when = self._clock() + self._settings.delay_after(job.attempts)
            self._queue.retry(job.retry_at(when, detail), document)
            return
        self._queue.fail(job.fail(detail), document)
        if self._summaries is not None:
            self._summaries.fail(document.id, SUMMARY_FAILED)
