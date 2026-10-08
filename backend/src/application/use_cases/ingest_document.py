"""Envio, substituicao e reprocessamento de documentos (RF-48, RF-51, RF-54).

Os tres so validam, guardam o original e enfileiram: extracao, vetorizacao e
gravacao no indice ficam com o worker (``ProcessNextIngestionJobUseCase``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import uuid4

from src.application.dto import DocumentAccessDTO
from src.application.services import (
    PIPELINE_VERSION,
    AccessControl,
    DocumentIndexer,
    is_index_outdated,
    read_index_state,
)
from src.application.services.document_indexing import hash_content
from src.domain import (
    AssistantId,
    AuditAction,
    AuditResource,
    AuthenticatedUser,
    Document,
    DocumentFileStorage,
    DocumentId,
    DocumentMetadata,
    DocumentRepository,
    DocumentStatus,
    DuplicateDocumentError,
    IndexOutdatedError,
    IngestionJob,
    IngestionJobKind,
    IngestionJobQueue,
    InvalidDocumentStateError,
    VectorStoreGateway,
    normalize_groups,
)

from .manage_assistant_access import DocumentNotFoundError

logger = logging.getLogger(__name__)


class DocumentTooLargeError(ValueError):
    """O arquivo enviado excede o limite configurado (RN-30)."""


@dataclass(frozen=True, slots=True)
class _Upload:
    source_name: str
    raw_content: bytes
    content_type: str | None


class _DocumentIntake:
    """Validacoes e gravacoes comuns ao envio e a substituicao."""

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        vector_store_gateway: VectorStoreGateway,
        document_indexer: DocumentIndexer,
        file_storage: DocumentFileStorage,
        job_queue: IngestionJobQueue,
        max_file_bytes: int,
        access_control: AccessControl,
    ) -> None:
        if max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be positive.")
        self.documents = document_repository
        self.vector_store = vector_store_gateway
        self.indexer = document_indexer
        self.storage = file_storage
        self.queue = job_queue
        self.max_file_bytes = max_file_bytes
        self.access = access_control

    def validate(self, assistant_id: AssistantId, upload: _Upload) -> str:
        """Recusa, antes de qualquer gravacao, o que nunca seria indexado.

        Devolve o hash do conteudo. Arquivo sem texto so e descoberto pelo
        worker, que o leva ao estado ``falhou``.
        """
        if len(upload.raw_content) > self.max_file_bytes:
            raise DocumentTooLargeError(
                f"file exceeds the limit of {self.max_file_bytes} bytes."
            )
        if not upload.raw_content:
            raise ValueError("uploaded file is empty.")
        # O worker identifica o formato so pelo nome: a extensao e obrigatoria.
        if not (
            self.indexer.supports(
                source_name=upload.source_name,
                content_type=upload.content_type,
            )
            and self.indexer.supports(
                source_name=upload.source_name,
                content_type=None,
            )
        ):
            raise ValueError(
                "unsupported file format. Supported formats: "
                ".txt, .md, .markdown, .pdf, .doc, .docx"
            )
        self._require_current_index(assistant_id)
        content_hash = hash_content(upload.raw_content)
        existing = self.documents.find_by_hash(assistant_id, content_hash)
        if existing is not None:
            raise DuplicateDocumentError(
                "the assistant already has a document with the same content.",
                existing_document_id=existing.id.value,
                existing_source_name=existing.source_name,
            )
        return content_hash

    def _require_current_index(self, assistant_id: AssistantId) -> None:
        """RN-16: base de outro modelo exige reindexacao antes de novos envios.

        Reindexacao em curso nao impede o envio (D8): o job espera o fim dela.
        """
        state = read_index_state(self.vector_store, assistant_id)
        outdated = is_index_outdated(
            state,
            self.documents.list_by_assistant(assistant_id),
            embedding_model=self.indexer.embedding_model,
            pipeline_version=PIPELINE_VERSION,
        )
        if outdated:
            raise IndexOutdatedError(
                "the assistant index is outdated; reindex before adding documents."
            )

    def register(
        self,
        document: Document,
        upload: _Upload,
        groups: frozenset[str],
    ) -> Document:
        """Guarda o original, o documento pendente, os grupos e o job.

        Os grupos sao gravados antes do job (C6): o worker ja encontra a
        restricao e nunca grava trechos abertos a todo o assistente.
        """
        storage_key = self.storage.save(
            assistant_id=document.assistant_id,
            document_id=document.id,
            filename=upload.source_name,
            content=upload.raw_content,
        )
        saved = self.documents.save(
            Document(
                id=document.id,
                assistant_id=document.assistant_id,
                source_name=document.source_name,
                content_hash=document.content_hash,
                metadata=document.metadata,
                status=DocumentStatus.PENDING,
                storage_key=storage_key,
                size_bytes=len(upload.raw_content),
                version=document.version,
                replaces_document_id=document.replaces_document_id,
                uploaded_by=document.uploaded_by,
            )
        )
        try:
            if groups:
                self.access.permissions.set_document_groups(saved.id, groups)
            self.queue.enqueue(
                IngestionJob(id=str(uuid4()), document_id=saved.id)
            )
        except Exception:
            # Sem job o documento ficaria pendente para sempre.
            self.documents.delete(saved.id)
            self._discard_file(storage_key)
            raise
        return saved

    def _discard_file(self, storage_key: str) -> None:
        try:
            self.storage.delete(storage_key)
        except Exception:  # noqa: BLE001 - o erro original e o relevante
            logger.exception(
                "document.original.discard_failed",
                extra={"storage_key": storage_key},
            )


@dataclass(frozen=True, slots=True)
class IngestDocumentInput:
    user: AuthenticatedUser
    assistant_id: str
    source_name: str
    raw_content: bytes
    content_type: str | None = None
    metadata: dict[str, str] | None = None
    document_id: str | None = None
    # Grupos a que o documento ja nasce restrito (D8 da SPEC-004); vazio segue
    # o assistente.
    groups: tuple[str, ...] = ()


class IngestDocumentUseCase:
    """RF-48: aceita o arquivo e responde com o documento pendente."""

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        vector_store_gateway: VectorStoreGateway,
        document_indexer: DocumentIndexer,
        file_storage: DocumentFileStorage,
        job_queue: IngestionJobQueue,
        max_file_bytes: int,
        access_control: AccessControl,
    ) -> None:
        self._intake = _DocumentIntake(
            document_repository=document_repository,
            vector_store_gateway=vector_store_gateway,
            document_indexer=document_indexer,
            file_storage=file_storage,
            job_queue=job_queue,
            max_file_bytes=max_file_bytes,
            access_control=access_control,
        )
        self._access = access_control

    def execute(self, data: IngestDocumentInput) -> DocumentAccessDTO:
        """RN-21: envia quem gerencia documentos do assistente."""
        assistant_id = AssistantId(data.assistant_id)
        self._access.require_document_management(
            data.user, assistant_id, AuditAction.DOCUMENT_UPLOADED
        )
        upload = _Upload(data.source_name, data.raw_content, data.content_type)
        content_hash = self._intake.validate(assistant_id, upload)
        groups = normalize_groups(data.groups)
        document = self._intake.register(
            Document(
                id=DocumentId(data.document_id or str(uuid4())),
                assistant_id=assistant_id,
                source_name=data.source_name,
                content_hash=content_hash,
                metadata=DocumentMetadata.from_dict(data.metadata),
                status=DocumentStatus.PENDING,
                uploaded_by=data.user.id,
            ),
            upload,
            groups,
        )
        self._access.audit(
            data.user,
            AuditAction.DOCUMENT_UPLOADED,
            resource_type=AuditResource.DOCUMENT,
            resource_id=document.id.value,
            details={
                "assistant_id": assistant_id.value,
                "source_name": document.source_name,
                "content_hash": document.content_hash,
                "size_bytes": document.size_bytes,
                "groups": sorted(groups),
            },
        )
        return DocumentAccessDTO.from_entity(document, groups)


@dataclass(frozen=True, slots=True)
class ReplaceDocumentInput:
    user: AuthenticatedUser
    document_id: str
    source_name: str
    raw_content: bytes
    content_type: str | None = None
    new_document_id: str | None = None


class ReplaceDocumentUseCase:
    """RF-51: envia nova versao; a anterior responde ate a nova ser indexada.

    A nova versao e outro documento, ligado ao anterior, com os mesmos grupos
    (C6) e os mesmos metadados.
    """

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        vector_store_gateway: VectorStoreGateway,
        document_indexer: DocumentIndexer,
        file_storage: DocumentFileStorage,
        job_queue: IngestionJobQueue,
        max_file_bytes: int,
        access_control: AccessControl,
    ) -> None:
        self._intake = _DocumentIntake(
            document_repository=document_repository,
            vector_store_gateway=vector_store_gateway,
            document_indexer=document_indexer,
            file_storage=file_storage,
            job_queue=job_queue,
            max_file_bytes=max_file_bytes,
            access_control=access_control,
        )
        self._documents = document_repository
        self._access = access_control

    def execute(self, data: ReplaceDocumentInput) -> DocumentAccessDTO:
        current = self._documents.get_by_id(DocumentId(data.document_id))
        if current is None or current.status is DocumentStatus.REPLACED:
            raise DocumentNotFoundError("document not found.")
        assistant_id = current.assistant_id
        self._access.require_document_management(
            data.user, assistant_id, AuditAction.DOCUMENT_REPLACED
        )
        if current.status is not DocumentStatus.INDEXED:
            raise InvalidDocumentStateError(
                "only indexed documents can receive a new version."
            )
        if self._pending_replacement(current) is not None:
            raise InvalidDocumentStateError(
                "a new version of this document is already being processed."
            )
        upload = _Upload(data.source_name, data.raw_content, data.content_type)
        content_hash = self._intake.validate(assistant_id, upload)
        groups = self._access.permissions.get_document_groups(current.id)
        document = self._intake.register(
            Document(
                id=DocumentId(data.new_document_id or str(uuid4())),
                assistant_id=assistant_id,
                source_name=data.source_name,
                content_hash=content_hash,
                metadata=current.metadata,
                status=DocumentStatus.PENDING,
                version=current.version + 1,
                replaces_document_id=current.id,
                uploaded_by=data.user.id,
            ),
            upload,
            groups,
        )
        self._access.audit(
            data.user,
            AuditAction.DOCUMENT_REPLACED,
            resource_type=AuditResource.DOCUMENT,
            resource_id=current.id.value,
            details={
                "assistant_id": assistant_id.value,
                "source_name": current.source_name,
                "new_document_id": document.id.value,
                "new_source_name": document.source_name,
                "content_hash": document.content_hash,
                "version": document.version,
            },
        )
        return DocumentAccessDTO.from_entity(document, groups)

    def _pending_replacement(self, current: Document) -> Document | None:
        return next(
            (
                item
                for item in self._documents.list_by_assistant(current.assistant_id)
                if item.replaces_document_id == current.id and item.is_in_progress
            ),
            None,
        )


@dataclass(frozen=True, slots=True)
class ReprocessDocumentInput:
    user: AuthenticatedUser
    document_id: str


class ReprocessDocumentUseCase:
    """RF-54: documento que falhou volta a fila a partir do original guardado."""

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        job_queue: IngestionJobQueue,
        access_control: AccessControl,
    ) -> None:
        self._documents = document_repository
        self._queue = job_queue
        self._access = access_control

    def execute(self, data: ReprocessDocumentInput) -> DocumentAccessDTO:
        document = self._documents.get_by_id(DocumentId(data.document_id))
        if document is None or document.status is DocumentStatus.REPLACED:
            raise DocumentNotFoundError("document not found.")
        self._access.require_document_management(
            data.user, document.assistant_id, AuditAction.DOCUMENT_REPROCESSED
        )
        if document.status is not DocumentStatus.FAILED:
            raise InvalidDocumentStateError(
                "only documents that failed can be reprocessed."
            )
        pending = self._documents.save(document.request_processing())
        try:
            self._queue.enqueue(
                IngestionJob(
                    id=str(uuid4()),
                    document_id=pending.id,
                    kind=IngestionJobKind.REPROCESS,
                )
            )
        except Exception:
            # Sem job o documento ficaria pendente para sempre.
            self._documents.save(document)
            raise
        self._access.audit(
            data.user,
            AuditAction.DOCUMENT_REPROCESSED,
            resource_type=AuditResource.DOCUMENT,
            resource_id=pending.id.value,
            details={
                "assistant_id": pending.assistant_id.value,
                "source_name": pending.source_name,
                "previous_failure": document.failure_reason,
            },
        )
        groups = self._access.permissions.get_document_groups(pending.id)
        return DocumentAccessDTO.from_entity(pending, groups)
