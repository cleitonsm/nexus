from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from src.application.dto import DocumentIngestionDTO
from src.application.services import (
    PIPELINE_VERSION,
    AccessControl,
    DocumentIndexer,
    IndexState,
    is_index_outdated,
    read_index_state,
)
from src.application.services.document_indexing import hash_content
from src.domain import (
    AssistantId,
    AuditAction,
    AuditResource,
    AuthenticatedUser,
    CollectionName,
    Document,
    DocumentFileStorage,
    DocumentId,
    DocumentMetadata,
    DocumentRepository,
    IndexOutdatedError,
    ReindexInProgressError,
    ReindexJobRepository,
    VectorStoreGateway,
    normalize_groups,
)


class DocumentTooLargeError(ValueError):
    """O arquivo enviado excede o limite configurado."""


@dataclass(frozen=True, slots=True)
class IngestDocumentInput:
    user: AuthenticatedUser
    assistant_id: str
    source_name: str
    raw_content: bytes
    content_type: str | None = None
    metadata: dict[str, str] | None = None
    document_id: str | None = None
    # Grupos a que o documento ja nasce restrito (D8); vazio segue o assistente.
    groups: tuple[str, ...] = ()


class IngestDocumentUseCase:
    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        vector_store_gateway: VectorStoreGateway,
        document_indexer: DocumentIndexer,
        file_storage: DocumentFileStorage,
        reindex_job_repository: ReindexJobRepository,
        max_file_bytes: int,
        access_control: AccessControl,
    ) -> None:
        if max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be positive.")
        self._document_repository = document_repository
        self._vector_store_gateway = vector_store_gateway
        self._document_indexer = document_indexer
        self._file_storage = file_storage
        self._reindex_job_repository = reindex_job_repository
        self._max_file_bytes = max_file_bytes
        self._access = access_control

    def execute(self, data: IngestDocumentInput) -> DocumentIngestionDTO:
        """RN-21: envia quem gerencia documentos do assistente.

        Com ``groups``, os trechos ja sao gravados restritos (D8): o documento
        nunca fica visivel a todo o assistente, nem por um instante.
        """
        self._access.require_document_management(
            data.user,
            AssistantId(data.assistant_id),
            AuditAction.DOCUMENT_UPLOADED,
        )
        if len(data.raw_content) > self._max_file_bytes:
            raise DocumentTooLargeError(
                f"file exceeds the limit of {self._max_file_bytes} bytes."
            )
        assistant_id = AssistantId(data.assistant_id)
        document_id = DocumentId(data.document_id or str(uuid4()))
        metadata = DocumentMetadata.from_dict(data.metadata)
        groups = normalize_groups(data.groups)
        state = self._writable_index_state(assistant_id)

        chunks = self._document_indexer.build_chunks(
            assistant_id=assistant_id,
            document_id=document_id,
            source_name=data.source_name,
            content_type=data.content_type,
            raw_content=data.raw_content,
            allowed_groups=groups,
        )
        storage_key = self._file_storage.save(
            assistant_id=assistant_id,
            document_id=document_id,
            filename=data.source_name,
            content=data.raw_content,
        )
        collection = self._ensure_collection(state)
        self._vector_store_gateway.upsert_chunks(
            collection_name=collection,
            chunks=chunks,
        )
        document = self._document_repository.save(
            Document(
                id=document_id,
                assistant_id=assistant_id,
                source_name=data.source_name,
                content_hash=hash_content(data.raw_content),
                metadata=metadata,
                embedding_model=self._document_indexer.embedding_model,
                pipeline_version=PIPELINE_VERSION,
                chunk_count=len(chunks),
                storage_key=storage_key,
            )
        )
        if groups:
            # Os trechos ja estao restritos; o banco guarda a mesma restricao
            # para a tela e para a reindexacao.
            self._access.permissions.set_document_groups(document_id, groups)
        self._access.audit(
            data.user,
            AuditAction.DOCUMENT_UPLOADED,
            resource_type=AuditResource.DOCUMENT,
            resource_id=document.id.value,
            details={
                "assistant_id": assistant_id.value,
                "source_name": document.source_name,
                "content_hash": document.content_hash,
                "chunk_count": len(chunks),
                "groups": sorted(groups),
            },
        )
        return DocumentIngestionDTO.from_entity(
            document,
            collection_name=state.alias.value,
            chunk_count=len(chunks),
            embedding_dimension=self._document_indexer.embedding_dimension,
            groups=groups,
        )

    def _writable_index_state(self, assistant_id: AssistantId) -> IndexState:
        if self._reindex_job_repository.get_running(assistant_id) is not None:
            raise ReindexInProgressError(
                "a reindex is in progress for this assistant."
            )
        state = read_index_state(self._vector_store_gateway, assistant_id)
        outdated = is_index_outdated(
            state,
            self._document_repository.list_by_assistant(assistant_id),
            embedding_model=self._document_indexer.embedding_model,
            pipeline_version=PIPELINE_VERSION,
        )
        if outdated:
            raise IndexOutdatedError(
                "the assistant index is outdated; reindex before adding documents."
            )
        return state

    def _ensure_collection(self, state: IndexState) -> CollectionName:
        """Devolve o alias, criando a primeira versao quando ainda nao existe."""
        if state.current is None:
            first = state.next_collection()
            self._vector_store_gateway.ensure_collection(
                collection_name=first,
                vector_size=self._document_indexer.embedding_dimension,
            )
            self._vector_store_gateway.point_alias(state.alias, first)
        return state.alias
