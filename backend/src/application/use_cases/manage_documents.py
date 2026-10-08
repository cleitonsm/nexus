"""Consulta e exclusao de documentos (RF-49, RF-50)."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dto import DocumentAccessDTO
from src.application.services import AccessControl
from src.domain import (
    AuditAction,
    AuditResource,
    AuthenticatedUser,
    CollectionName,
    Document,
    DocumentFileStorage,
    DocumentId,
    DocumentRepository,
    DocumentStatus,
    ReindexInProgressError,
    ReindexJobRepository,
    VectorStoreGateway,
)

from .manage_assistant_access import DocumentNotFoundError


@dataclass(frozen=True, slots=True)
class DocumentRefInput:
    user: AuthenticatedUser
    document_id: str


class GetDocumentUseCase:
    """Estado atual do documento, consultado pela tela enquanto ele processa."""

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        access_control: AccessControl,
    ) -> None:
        self._documents = document_repository
        self._access = access_control

    def execute(self, data: DocumentRefInput) -> DocumentAccessDTO:
        document = self._documents.get_by_id(DocumentId(data.document_id))
        if document is None or document.status is DocumentStatus.REPLACED:
            raise DocumentNotFoundError("document not found.")
        self._access.require_document_management(
            data.user, document.assistant_id, "document.read"
        )
        groups = self._access.permissions.get_document_groups(document.id)
        return DocumentAccessDTO.from_entity(document, groups)


class DeleteDocumentUseCase:
    """RF-50, RN-29: remove trechos, arquivo e registro do documento.

    Uma nova versao ainda em processamento sai junto: sem a versao vigente, ela
    nao teria o que substituir. O worker que estiver processando o documento
    percebe a exclusao antes de ativar os trechos (C4).
    """

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        vector_store_gateway: VectorStoreGateway,
        file_storage: DocumentFileStorage,
        reindex_job_repository: ReindexJobRepository,
        access_control: AccessControl,
    ) -> None:
        self._documents = document_repository
        self._vector_store = vector_store_gateway
        self._storage = file_storage
        self._reindex_jobs = reindex_job_repository
        self._access = access_control

    def execute(self, data: DocumentRefInput) -> None:
        document = self._documents.get_by_id(DocumentId(data.document_id))
        if document is None or document.status is DocumentStatus.REPLACED:
            raise DocumentNotFoundError("document not found.")
        assistant_id = document.assistant_id
        self._access.require_document_management(
            data.user, assistant_id, AuditAction.DOCUMENT_DELETED
        )
        # A collection em construcao ja copiou este documento; exclui-lo agora
        # o faria reaparecer quando o alias fosse trocado.
        if self._reindex_jobs.get_running(assistant_id) is not None:
            raise ReindexInProgressError(
                "a reindex is in progress for this assistant."
            )
        removed = [document, *self._pending_versions(document)]
        collection = CollectionName.from_assistant_id(assistant_id)
        for item in removed:
            self._vector_store.delete_by_document(collection, item.id)
        # Trechos, depois arquivo, por ultimo o registro: se algo falhar no
        # meio, o documento continua listado e a exclusao pode ser repetida.
        for item in removed:
            if item.storage_key:
                self._storage.delete(item.storage_key)
            self._documents.delete(item.id)
        self._access.audit(
            data.user,
            AuditAction.DOCUMENT_DELETED,
            resource_type=AuditResource.DOCUMENT,
            resource_id=document.id.value,
            details={
                "assistant_id": assistant_id.value,
                "source_name": document.source_name,
                "status": document.status.value,
                "version": document.version,
                "pending_versions_removed": [item.id.value for item in removed[1:]],
            },
        )

    def _pending_versions(self, document: Document) -> list[Document]:
        return [
            item
            for item in self._documents.list_by_assistant(document.assistant_id)
            if item.replaces_document_id == document.id
        ]
