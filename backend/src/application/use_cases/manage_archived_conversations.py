"""Conversas anteriores a autenticacao (decisao PC-D5, ajusta a D3 da SPEC-004).

Ficam sem dono e fora das listas dos usuarios. So o administrador as lista,
le e exclui: no MVP elas eram visiveis a qualquer pessoa, e nenhuma pessoa
pode reivindica-las como suas. Cada consulta, leitura e exclusao entra na
trilha de auditoria.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dto import ConversationDTO
from src.application.services import AccessControl
from src.domain import (
    AuditAction,
    AuditResource,
    AuthenticatedUser,
    Conversation,
    ConversationId,
    ConversationRepository,
)

from .chat_with_assistant import ConversationNotFoundError


@dataclass(frozen=True, slots=True)
class ArchivedConversationInput:
    user: AuthenticatedUser
    conversation_id: str


class ListArchivedConversationsUseCase:
    def __init__(
        self,
        repository: ConversationRepository,
        access_control: AccessControl,
    ) -> None:
        self._repository = repository
        self._access = access_control

    def execute(self, user: AuthenticatedUser) -> list[ConversationDTO]:
        self._access.require_admin(user, AuditAction.ARCHIVED_CONVERSATIONS_CONSULTED)
        conversations = self._repository.list_archived()
        self._access.audit(
            user,
            AuditAction.ARCHIVED_CONVERSATIONS_CONSULTED,
            resource_type=AuditResource.CONVERSATION,
            details={"count": len(conversations)},
        )
        return [ConversationDTO.from_entity(item) for item in conversations]


def _load_archived(
    repository: ConversationRepository,
    conversation_id: str,
) -> Conversation:
    """Conversa com dono responde como inexistente: nao vaza conversa privada."""
    conversation = repository.get_by_id(ConversationId(conversation_id))
    if conversation is None or not conversation.is_archived:
        raise ConversationNotFoundError("archived conversation not found.")
    return conversation


class GetArchivedConversationUseCase:
    def __init__(
        self,
        repository: ConversationRepository,
        access_control: AccessControl,
    ) -> None:
        self._repository = repository
        self._access = access_control

    def execute(self, data: ArchivedConversationInput) -> Conversation:
        self._access.require_admin(data.user, AuditAction.ARCHIVED_CONVERSATION_VIEWED)
        conversation = _load_archived(self._repository, data.conversation_id)
        self._access.audit(
            data.user,
            AuditAction.ARCHIVED_CONVERSATION_VIEWED,
            resource_type=AuditResource.CONVERSATION,
            resource_id=conversation.id.value,
            details={"assistant_id": conversation.assistant_id.value},
        )
        return conversation


class DeleteArchivedConversationUseCase:
    def __init__(
        self,
        repository: ConversationRepository,
        access_control: AccessControl,
    ) -> None:
        self._repository = repository
        self._access = access_control

    def execute(self, data: ArchivedConversationInput) -> None:
        self._access.require_admin(data.user, AuditAction.ARCHIVED_CONVERSATION_DELETED)
        conversation = _load_archived(self._repository, data.conversation_id)
        if not self._repository.delete(conversation.id):
            raise ConversationNotFoundError("archived conversation not found.")
        self._access.audit(
            data.user,
            AuditAction.ARCHIVED_CONVERSATION_DELETED,
            resource_type=AuditResource.CONVERSATION,
            resource_id=conversation.id.value,
            details={
                "assistant_id": conversation.assistant_id.value,
                "message_count": len(conversation.messages),
            },
        )
