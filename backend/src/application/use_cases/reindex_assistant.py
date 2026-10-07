from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import uuid4

from src.application.dto import IndexStatusDTO, ReindexJobDTO
from src.application.services import (
    PIPELINE_VERSION,
    DocumentIndexer,
    IndexState,
    is_index_outdated,
    read_index_state,
)
from src.domain import (
    AssistantId,
    CollectionName,
    Document,
    DocumentFileStorage,
    DocumentRepository,
    EmbeddingGateway,
    ReindexInProgressError,
    ReindexJob,
    ReindexJobRepository,
    VectorStoreGateway,
)

logger = logging.getLogger(__name__)

INTERRUPTED_MESSAGE = "reindex interrupted by an application restart."


class ReindexJobNotFoundError(LookupError):
    """A reindexacao informada nao existe."""


@dataclass(frozen=True, slots=True)
class StartReindexInput:
    assistant_id: str


class StartReindexUseCase:
    """Registra a reindexacao; a execucao fica com ``RunReindexUseCase``."""

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        vector_store_gateway: VectorStoreGateway,
        reindex_job_repository: ReindexJobRepository,
    ) -> None:
        self._document_repository = document_repository
        self._vector_store_gateway = vector_store_gateway
        self._reindex_job_repository = reindex_job_repository

    def execute(self, data: StartReindexInput) -> ReindexJobDTO:
        assistant_id = AssistantId(data.assistant_id)
        if self._reindex_job_repository.get_running(assistant_id) is not None:
            raise ReindexInProgressError(
                "a reindex is already in progress for this assistant."
            )
        state = read_index_state(self._vector_store_gateway, assistant_id)
        documents = self._document_repository.list_by_assistant(assistant_id)
        job = self._reindex_job_repository.save(
            ReindexJob(
                id=str(uuid4()),
                assistant_id=assistant_id,
                target_collection=state.next_collection().value,
                total_documents=len(documents),
            )
        )
        return ReindexJobDTO.from_entity(job)


@dataclass(frozen=True, slots=True)
class RunReindexInput:
    job_id: str


class RunReindexUseCase:
    """Constroi a nova versao da collection e troca o alias (RF-31).

    Falhas de processamento nao sao propagadas: ficam registradas na
    reindexacao, a collection parcial e descartada e o alias nao muda.
    """

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        vector_store_gateway: VectorStoreGateway,
        document_indexer: DocumentIndexer,
        file_storage: DocumentFileStorage,
        reindex_job_repository: ReindexJobRepository,
    ) -> None:
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
            if document.has_original
        ]
        self._discard(target)
        self._vector_store_gateway.ensure_collection(
            collection_name=target,
            vector_size=self._document_indexer.embedding_dimension,
        )
        reindexed: list[Document] = []
        for document in documents:
            reindexed.append(self._reindex_document(document, target))
            self._reindex_job_repository.save(
                job.with_progress(
                    total=job.total_documents,
                    processed=len(reindexed),
                )
            )
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
    ) -> Document:
        chunks = self._document_indexer.build_chunks(
            assistant_id=document.assistant_id,
            document_id=document.id,
            source_name=document.source_name,
            content_type=None,
            raw_content=self._file_storage.load(document.storage_key or ""),
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


class FailInterruptedReindexesUseCase:
    """Na subida da aplicacao, encerra reindexacoes que ficaram em curso."""

    def __init__(
        self,
        *,
        vector_store_gateway: VectorStoreGateway,
        reindex_job_repository: ReindexJobRepository,
    ) -> None:
        self._vector_store_gateway = vector_store_gateway
        self._reindex_job_repository = reindex_job_repository

    def execute(self) -> int:
        interrupted = self._reindex_job_repository.list_running()
        for job in interrupted:
            target = CollectionName(job.target_collection)
            alias = CollectionName.from_assistant_id(job.assistant_id)
            in_use = self._vector_store_gateway.resolve_alias(alias) == target
            if not in_use and self._vector_store_gateway.collection_exists(target):
                self._vector_store_gateway.delete_collection(target)
            self._reindex_job_repository.save(job.fail(INTERRUPTED_MESSAGE))
        return len(interrupted)


@dataclass(frozen=True, slots=True)
class GetIndexStatusInput:
    assistant_id: str


class GetIndexStatusUseCase:
    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        vector_store_gateway: VectorStoreGateway,
        embedding_gateway: EmbeddingGateway,
        reindex_job_repository: ReindexJobRepository,
    ) -> None:
        self._document_repository = document_repository
        self._vector_store_gateway = vector_store_gateway
        self._embedding_gateway = embedding_gateway
        self._reindex_job_repository = reindex_job_repository

    def execute(self, data: GetIndexStatusInput) -> IndexStatusDTO:
        assistant_id = AssistantId(data.assistant_id)
        state = read_index_state(self._vector_store_gateway, assistant_id)
        documents = self._document_repository.list_by_assistant(assistant_id)
        model = self._embedding_gateway.model_name
        last_job = self._reindex_job_repository.get_latest(assistant_id)
        collection = state.current or (state.alias if state.legacy else None)
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
        )
