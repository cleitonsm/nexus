"""Exclusao de assistentes e vinculos com grupos (RF-42, RF-43)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.application.dto import DocumentAccessDTO
from src.application.services import AccessControl, ensure_known_groups
from src.domain import (
    AssistantId,
    AssistantRepository,
    AuditAction,
    AuditResource,
    AuthenticatedUser,
    CollectionName,
    Document,
    DocumentFileStorage,
    DocumentId,
    DocumentRepository,
    GroupDirectory,
    ReindexInProgressError,
    ReindexJobRepository,
    VectorStoreGateway,
    normalize_groups,
)

logger = logging.getLogger(__name__)


class AssistantNotFoundError(LookupError):
    """O assistente informado nao existe."""


class DocumentNotFoundError(LookupError):
    """O documento informado nao existe."""


@dataclass(frozen=True, slots=True)
class DeleteAssistantInput:
    user: AuthenticatedUser
    assistant_id: str


class DeleteAssistantUseCase:
    """RF-96, RN-44 a RN-46 (SPEC-014): exclui o assistente e a base vetorial.

    Ordem: collection vigente, originais dos documentos e, por ultimo, o
    registro (o PostgreSQL apaga documentos, jobs e conversas em cascata). Se
    algo falhar antes do registro, o assistente continua listado e a exclusao
    pode ser repetida.
    """

    def __init__(
        self,
        *,
        assistant_repository: AssistantRepository,
        vector_store_gateway: VectorStoreGateway,
        access_control: AccessControl,
        document_repository: DocumentRepository,
        file_storage: DocumentFileStorage,
        reindex_job_repository: ReindexJobRepository,
    ) -> None:
        self._assistant_repository = assistant_repository
        self._vector_store_gateway = vector_store_gateway
        self._access = access_control
        self._documents = document_repository
        self._storage = file_storage
        self._reindex_jobs = reindex_job_repository

    def execute(self, data: DeleteAssistantInput) -> None:
        self._access.require_admin(data.user, AuditAction.ASSISTANT_DELETED)
        assistant_id = AssistantId(data.assistant_id)
        assistant = self._assistant_repository.get_by_id(assistant_id)
        if assistant is None:
            raise AssistantNotFoundError("assistant not found.")
        # RN-45: o worker trocaria o alias depois e recriaria a base.
        if self._reindex_jobs.get_running(assistant_id) is not None:
            raise ReindexInProgressError(
                "a reindex is in progress for this assistant."
            )
        documents = self._documents.list_by_assistant(assistant_id)
        # O nome do assistente e um alias; a collection vigente e versionada.
        alias = CollectionName.from_assistant_id(assistant_id)
        collection = self._vector_store_gateway.resolve_alias(alias) or alias
        self._vector_store_gateway.delete_collection(collection)
        for document in documents:
            self._discard_original(document)
        if not self._assistant_repository.delete(assistant_id):
            raise AssistantNotFoundError("assistant not found.")
        self._access.audit(
            data.user,
            AuditAction.ASSISTANT_DELETED,
            resource_type=AuditResource.ASSISTANT,
            resource_id=assistant_id.value,
            details={
                "assistant_id": assistant_id.value,
                "name": assistant.name.value,
                "collection": collection.value,
                "documents_removed": len(documents),
            },
        )

    def _discard_original(self, document: Document) -> None:
        if not document.storage_key:
            return
        try:
            self._storage.delete(document.storage_key)
        except Exception:  # noqa: BLE001 - o arquivo orfao nao afeta as buscas
            logger.exception(
                "assistant.delete.original_failed",
                extra={
                    "assistant_id": document.assistant_id.value,
                    "document_id": document.id.value,
                },
            )


@dataclass(frozen=True, slots=True)
class SetAssistantGroupsInput:
    user: AuthenticatedUser
    assistant_id: str
    groups: tuple[str, ...]


class SetAssistantGroupsUseCase:
    """RF-42: define, por substituicao, os grupos que usam o assistente.

    Lista vazia devolve o assistente ao acesso exclusivo de administradores.
    """

    def __init__(
        self,
        *,
        assistant_repository: AssistantRepository,
        access_control: AccessControl,
    ) -> None:
        self._assistant_repository = assistant_repository
        self._access = access_control

    def execute(self, data: SetAssistantGroupsInput) -> tuple[str, ...]:
        self._access.require_admin(data.user, AuditAction.ASSISTANT_GROUPS_CHANGED)
        assistant_id = AssistantId(data.assistant_id)
        if self._assistant_repository.get_by_id(assistant_id) is None:
            raise AssistantNotFoundError("assistant not found.")
        groups = normalize_groups(data.groups)
        permissions = self._access.permissions
        before = permissions.get_assistant_groups(assistant_id)
        permissions.set_assistant_groups(assistant_id, groups)
        self._access.audit(
            data.user,
            AuditAction.ASSISTANT_GROUPS_CHANGED,
            resource_type=AuditResource.ASSISTANT,
            resource_id=assistant_id.value,
            details={
                "assistant_id": assistant_id.value,
                "before": sorted(before),
                "after": sorted(groups),
            },
        )
        return tuple(sorted(groups))


@dataclass(frozen=True, slots=True)
class ListDocumentsInput:
    user: AuthenticatedUser
    assistant_id: str


class ListDocumentsUseCase:
    """Documentos do assistente com a restricao de cada um (HU-25)."""

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        access_control: AccessControl,
    ) -> None:
        self._document_repository = document_repository
        self._access = access_control

    def execute(self, data: ListDocumentsInput) -> list[DocumentAccessDTO]:
        assistant_id = AssistantId(data.assistant_id)
        self._access.require_document_management(
            data.user, assistant_id, "document.list"
        )
        groups = self._access.permissions.list_document_groups(assistant_id)
        return [
            DocumentAccessDTO.from_entity(
                document,
                groups.get(document.id.value, frozenset()),
            )
            for document in self._document_repository.list_by_assistant(
                assistant_id
            )
        ]


@dataclass(frozen=True, slots=True)
class SetDocumentGroupsInput:
    user: AuthenticatedUser
    document_id: str
    groups: tuple[str, ...]


class SetDocumentGroupsUseCase:
    """RF-43: restringe um documento a grupos, sem reindexar vetores.

    A restricao so restringe (RN-23): quem nao acessa o assistente continua
    sem acesso, mesmo pertencendo a um grupo do documento. Lista vazia remove
    a restricao.
    """

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        vector_store_gateway: VectorStoreGateway,
        reindex_job_repository: ReindexJobRepository,
        access_control: AccessControl,
        group_directory: GroupDirectory | None = None,
    ) -> None:
        self._document_repository = document_repository
        self._vector_store_gateway = vector_store_gateway
        self._reindex_job_repository = reindex_job_repository
        self._access = access_control
        self._group_directory = group_directory

    def execute(self, data: SetDocumentGroupsInput) -> DocumentAccessDTO:
        document_id = DocumentId(data.document_id)
        document = self._document_repository.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError("document not found.")
        assistant_id = document.assistant_id
        self._access.require_document_management(
            data.user, assistant_id, AuditAction.DOCUMENT_GROUPS_CHANGED
        )
        # A collection em construcao ja copiou a restricao antiga deste
        # documento; alterar agora deixaria a nova versao desatualizada.
        if self._reindex_job_repository.get_running(assistant_id) is not None:
            raise ReindexInProgressError(
                "a reindex is in progress for this assistant."
            )
        groups = normalize_groups(data.groups)
        # RF-74: grupo desconhecido esconderia o documento de todos.
        ensure_known_groups(groups, self._group_directory)
        permissions = self._access.permissions
        before = permissions.get_document_groups(document_id)
        permissions.set_document_groups(document_id, groups)
        try:
            self._vector_store_gateway.set_document_groups(
                CollectionName.from_assistant_id(assistant_id),
                document_id,
                groups,
            )
        except Exception:
            # Banco e indice precisam concordar: sem o indice, vale o anterior.
            permissions.set_document_groups(document_id, before)
            raise
        self._access.audit(
            data.user,
            AuditAction.DOCUMENT_GROUPS_CHANGED,
            resource_type=AuditResource.DOCUMENT,
            resource_id=document_id.value,
            details={
                "assistant_id": assistant_id.value,
                "source_name": document.source_name,
                "before": sorted(before),
                "after": sorted(groups),
            },
        )
        return DocumentAccessDTO.from_entity(document, groups)
