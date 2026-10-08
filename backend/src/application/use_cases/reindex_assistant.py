from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.application.dto import IndexStatusDTO, ReindexJobDTO
from src.application.services import (
    PIPELINE_VERSION,
    AccessControl,
    DocumentIndexer,
    IndexState,
    check_sparse_parameters,
    is_index_outdated,
    read_index_state,
    record_sparse_parameters,
)
from src.domain import (
    AssistantId,
    AssistantPermissionRepository,
    AssistantRepository,
    AuditAction,
    AuditResource,
    AuthenticatedUser,
    CollectionName,
    Document,
    DocumentFileStorage,
    DocumentRepository,
    DocumentStatus,
    EmbeddingGateway,
    IndexParametersRepository,
    IngestionInProgressError,
    MetricsRecorder,
    ReindexInProgressError,
    ReindexJob,
    ReindexJobRepository,
    SparseEncodingParameters,
    VectorStoreGateway,
)

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)

INTERRUPTED_MESSAGE = (
    "reindex interrupted repeatedly (worker stopped before finishing); "
    "start a new reindex."
)
SPARSE_PARAMETERS_CHANGED_METRIC = "nexus_index_sparse_parameters_changed_total"


class ReindexJobNotFoundError(LookupError):
    """A reindexacao informada nao existe."""


@dataclass(frozen=True, slots=True)
class StartReindexInput:
    user: AuthenticatedUser
    assistant_id: str


class StartReindexUseCase:
    """Registra a reindexacao; a execucao fica com ``RunReindexUseCase``."""

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        vector_store_gateway: VectorStoreGateway,
        reindex_job_repository: ReindexJobRepository,
        access_control: AccessControl,
    ) -> None:
        self._document_repository = document_repository
        self._vector_store_gateway = vector_store_gateway
        self._reindex_job_repository = reindex_job_repository
        self._access = access_control

    def execute(self, data: StartReindexInput) -> ReindexJobDTO:
        assistant_id = AssistantId(data.assistant_id)
        self._access.require_document_management(
            data.user, assistant_id, AuditAction.ASSISTANT_REINDEX_STARTED
        )
        if self._reindex_job_repository.get_running(assistant_id) is not None:
            raise ReindexInProgressError(
                "a reindex is already in progress for this assistant."
            )
        state = read_index_state(self._vector_store_gateway, assistant_id)
        listed = self._document_repository.list_by_assistant(assistant_id)
        # O worker grava na collection vigente: trocar o alias agora perderia
        # esses trechos. Os pendentes esperam o fim da reindexacao (D8).
        if any(item.status is DocumentStatus.PROCESSING for item in listed):
            raise IngestionInProgressError(
                "documents of this assistant are being processed; "
                "try again when they finish."
            )
        documents = [item for item in listed if item.is_searchable]
        job = self._reindex_job_repository.save(
            ReindexJob(
                id=str(uuid4()),
                assistant_id=assistant_id,
                target_collection=state.next_collection().value,
                total_documents=len(documents),
            )
        )
        self._access.audit(
            data.user,
            AuditAction.ASSISTANT_REINDEX_STARTED,
            resource_type=AuditResource.ASSISTANT,
            resource_id=assistant_id.value,
            details={
                "assistant_id": assistant_id.value,
                "job_id": job.id,
                "total_documents": job.total_documents,
            },
        )
        return ReindexJobDTO.from_entity(job)


@dataclass(frozen=True, slots=True)
class RunReindexInput:
    job_id: str


class RunReindexUseCase:
    """Constroi a nova versao da collection e troca o alias (RF-31).

    Falhas de processamento nao sao propagadas: ficam registradas na
    reindexacao, a collection parcial e descartada e o alias nao muda.

    Roda em segundo plano, sem usuario: a autorizacao acontece em
    ``StartReindexUseCase``. Os trechos novos levam a restricao por grupo
    vigente de cada documento (RF-43). So documentos indexados entram; os
    pendentes sao processados pelo worker depois da troca do alias (D8).
    """

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        vector_store_gateway: VectorStoreGateway,
        document_indexer: DocumentIndexer,
        file_storage: DocumentFileStorage,
        reindex_job_repository: ReindexJobRepository,
        permission_repository: AssistantPermissionRepository,
        index_parameters: IndexParametersRepository | None = None,
        lease: timedelta | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._index_parameters = index_parameters
        # PC-D4: prazo da reserva do worker, renovado a cada documento.
        self._lease = lease
        self._clock = clock
        self._permission_repository = permission_repository
        self._document_repository = document_repository
        self._vector_store_gateway = vector_store_gateway
        self._document_indexer = document_indexer
        self._file_storage = file_storage
        self._reindex_job_repository = reindex_job_repository

    def execute(self, data: RunReindexInput) -> ReindexJobDTO:
        job = self._reindex_job_repository.get_by_id(data.job_id)
        if job is None:
            raise ReindexJobNotFoundError("reindex job not found.")
        if not job.is_running:
            return ReindexJobDTO.from_entity(job)

        target = CollectionName(job.target_collection)
        swapped = False
        try:
            state = read_index_state(self._vector_store_gateway, job.assistant_id)
            if state.current == target:
                raise RuntimeError("target collection is already in use.")
            reindexed = self._build_target(job, target)
            self._swap_alias(state, target)
            swapped = True
            for document in reindexed:
                self._document_repository.save(document)
            job = job.with_progress(
                total=job.total_documents,
                processed=len(reindexed),
            ).succeed()
        except Exception as exc:  # noqa: BLE001 - registra qualquer falha
            logger.exception(
                "reindex.failed",
                extra={"assistant_id": job.assistant_id.value, "job_id": job.id},
            )
            if not swapped:
                self._discard(target)
            job = job.fail(f"{type(exc).__name__}: {exc}")
        return ReindexJobDTO.from_entity(self._reindex_job_repository.save(job))

    def _build_target(
        self,
        job: ReindexJob,
        target: CollectionName,
    ) -> list[Document]:
        documents = [
            document
            for document in self._document_repository.list_by_assistant(
                job.assistant_id
            )
            if document.has_original and document.is_searchable
        ]
        self._discard(target)
        self._vector_store_gateway.ensure_collection(
            collection_name=target,
            vector_size=self._document_indexer.embedding_dimension,
        )
        # PC-D2: a nova versao nasce com os parametros do BM25 vigentes.
        record_sparse_parameters(
            self._index_parameters,
            target,
            self._document_indexer.sparse_parameters,
        )
        groups = self._permission_repository.list_document_groups(job.assistant_id)
        reindexed: list[Document] = []
        for document in documents:
            reindexed.append(
                self._reindex_document(
                    document,
                    target,
                    groups.get(document.id.value, frozenset()),
                )
            )
            progress = job.with_progress(
                total=job.total_documents,
                processed=len(reindexed),
            )
            if self._lease is not None:
                progress = progress.renew(self._clock(), self._lease)
            self._reindex_job_repository.save(progress)
        expected = sum(document.chunk_count for document in reindexed)
        stored = self._vector_store_gateway.count_points(target)
        if stored != expected:
            raise RuntimeError(
                f"chunk count mismatch: expected {expected}, stored {stored}."
            )
        return reindexed

    def _reindex_document(
        self,
        document: Document,
        target: CollectionName,
        allowed_groups: frozenset[str],
    ) -> Document:
        chunks = self._document_indexer.build_chunks(
            assistant_id=document.assistant_id,
            document_id=document.id,
            source_name=document.source_name,
            content_type=None,
            raw_content=self._file_storage.load(document.storage_key or ""),
            allowed_groups=allowed_groups,
        )
        self._vector_store_gateway.upsert_chunks(
            collection_name=target,
            chunks=chunks,
        )
        return document.indexed_with(
            embedding_model=self._document_indexer.embedding_model,
            pipeline_version=PIPELINE_VERSION,
            chunk_count=len(chunks),
        )

    def _swap_alias(self, state: IndexState, target: CollectionName) -> None:
        if state.legacy:
            # A collection do MVP ocupa o nome do alias: precisa sair antes.
            # E a unica indisponibilidade prevista, e ocorre uma unica vez.
            self._vector_store_gateway.delete_collection(state.alias)
        self._vector_store_gateway.point_alias(state.alias, target)
        if state.current is not None and state.current != target:
            self._vector_store_gateway.delete_collection(state.current)

    def _discard(self, collection: CollectionName) -> None:
        if self._vector_store_gateway.collection_exists(collection):
            self._vector_store_gateway.delete_collection(collection)


@dataclass(frozen=True, slots=True)
class ReindexSettings:
    """PC-D4: tentativas e prazo da reserva (renovado a cada documento).

    Reaproveita os valores da ingestao (D7 da SPEC-005): ``INGESTION_MAX_ATTEMPTS``
    e ``INGESTION_JOB_TIMEOUT_SECONDS``.
    """

    max_attempts: int = 3
    lease_seconds: int = 600

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        if self.lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive.")

    @property
    def lease(self) -> timedelta:
        return timedelta(seconds=self.lease_seconds)


class ProcessNextReindexJobUseCase:
    """PC-D4: o worker reserva uma reindexacao e a executa.

    A API so registra o pedido (``StartReindexUseCase``). Um job cujo prazo
    venceu (worker interrompido) e reservado de novo e recomeca do zero: a
    collection parcial e descartada por ``RunReindexUseCase``. Esgotadas as
    tentativas, o job falha, a collection parcial sai e o alias nao muda.
    """

    def __init__(
        self,
        *,
        reindex_job_repository: ReindexJobRepository,
        vector_store_gateway: VectorStoreGateway,
        run_reindex: Callable[[str, timedelta], ReindexJobDTO],
        settings: ReindexSettings | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._jobs = reindex_job_repository
        self._vector_store = vector_store_gateway
        self._run_reindex = run_reindex
        self._settings = settings or ReindexSettings()
        self._clock = clock

    def execute(self) -> ReindexJobDTO | None:
        """Processa um job; ``None`` quando nao ha reindexacao a fazer."""
        job = self._jobs.claim_next(self._clock(), self._settings.lease)
        if job is None:
            return None
        if job.attempts > self._settings.max_attempts:
            return ReindexJobDTO.from_entity(self._abandon(job))
        if job.attempts > 1:
            logger.warning(
                "reindex.resumed_after_interruption",
                extra={
                    "assistant_id": job.assistant_id.value,
                    "job_id": job.id,
                    "attempt": job.attempts,
                },
            )
        return self._run_reindex(job.id, self._settings.lease)

    def _abandon(self, job: ReindexJob) -> ReindexJob:
        target = CollectionName(job.target_collection)
        alias = CollectionName.from_assistant_id(job.assistant_id)
        in_use = self._vector_store.resolve_alias(alias) == target
        if not in_use and self._vector_store.collection_exists(target):
            self._vector_store.delete_collection(target)
        logger.error(
            "reindex.abandoned",
            extra={
                "assistant_id": job.assistant_id.value,
                "job_id": job.id,
                "attempts": job.attempts - 1,
            },
        )
        return self._jobs.save(job.fail(INTERRUPTED_MESSAGE))


@dataclass(frozen=True, slots=True)
class GetIndexStatusInput:
    user: AuthenticatedUser
    assistant_id: str


class GetIndexStatusUseCase:
    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        vector_store_gateway: VectorStoreGateway,
        embedding_gateway: EmbeddingGateway,
        reindex_job_repository: ReindexJobRepository,
        access_control: AccessControl,
        index_parameters: IndexParametersRepository | None = None,
        sparse_parameters: SparseEncodingParameters | None = None,
    ) -> None:
        self._access = access_control
        self._index_parameters = index_parameters
        self._sparse_parameters = sparse_parameters
        self._document_repository = document_repository
        self._vector_store_gateway = vector_store_gateway
        self._embedding_gateway = embedding_gateway
        self._reindex_job_repository = reindex_job_repository

    def execute(self, data: GetIndexStatusInput) -> IndexStatusDTO:
        assistant_id = AssistantId(data.assistant_id)
        self._access.require_document_management(
            data.user, assistant_id, "index.status"
        )
        state = read_index_state(self._vector_store_gateway, assistant_id)
        documents = self._document_repository.list_by_assistant(assistant_id)
        model = self._embedding_gateway.model_name
        last_job = self._reindex_job_repository.get_latest(assistant_id)
        collection = state.current or (state.alias if state.legacy else None)
        sparse = check_sparse_parameters(
            state, self._index_parameters, self._sparse_parameters
        )
        if sparse.changed:
            _warn_sparse_parameters_changed(assistant_id, sparse.recorded, sparse.current)
        return IndexStatusDTO(
            assistant_id=assistant_id.value,
            embedding_model=model,
            pipeline_version=PIPELINE_VERSION,
            collection_name=collection.value if collection else None,
            outdated=is_index_outdated(
                state,
                documents,
                embedding_model=model,
                pipeline_version=PIPELINE_VERSION,
            ),
            documents_total=len(documents),
            documents_indexed=sum(
                document.is_current(
                    embedding_model=model,
                    pipeline_version=PIPELINE_VERSION,
                )
                for document in documents
            ),
            documents_without_original=tuple(
                sorted(
                    document.source_name
                    for document in documents
                    if not document.has_original
                )
            ),
            last_reindex=ReindexJobDTO.from_entity(last_job) if last_job else None,
            sparse_parameters_changed=sparse.changed,
            sparse_parameters_recorded=(
                sparse.recorded.as_dict() if sparse.recorded else None
            ),
            sparse_parameters_current=(
                sparse.current.as_dict() if sparse.current else None
            ),
        )


def _warn_sparse_parameters_changed(
    assistant_id: AssistantId,
    recorded: SparseEncodingParameters | None,
    current: SparseEncodingParameters | None,
) -> None:
    logger.warning(
        "index.sparse_parameters_changed",
        extra={
            "assistant_id": assistant_id.value,
            "recorded": recorded.as_dict() if recorded else None,
            "current": current.as_dict() if current else None,
        },
    )


class ReportSparseParameterChangesUseCase:
    """PC-D2: na subida, aponta assistentes cujos vetores esparsos foram
    gerados com outros parametros do BM25.

    So avisa (log e metrica); a busca e os envios continuam. A correcao e
    reindexar o assistente. Sem usuario: roda na inicializacao da API.
    """

    def __init__(
        self,
        *,
        assistant_repository: AssistantRepository,
        vector_store_gateway: VectorStoreGateway,
        index_parameters: IndexParametersRepository,
        sparse_parameters: SparseEncodingParameters | None,
        metrics: MetricsRecorder | None = None,
    ) -> None:
        self._assistants = assistant_repository
        self._vector_store = vector_store_gateway
        self._index_parameters = index_parameters
        self._sparse_parameters = sparse_parameters
        self._metrics = metrics

    def execute(self) -> list[str]:
        changed: list[str] = []
        for assistant in self._assistants.list_all():
            state = read_index_state(self._vector_store, assistant.id)
            check = check_sparse_parameters(
                state, self._index_parameters, self._sparse_parameters
            )
            if not check.changed:
                continue
            changed.append(assistant.id.value)
            _warn_sparse_parameters_changed(assistant.id, check.recorded, check.current)
            if self._metrics is not None:
                self._metrics.increment(SPARSE_PARAMETERS_CHANGED_METRIC)
        return changed
