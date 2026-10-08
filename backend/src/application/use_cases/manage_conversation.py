"""Leitura, exclusao e mensagens avulsas de uma conversa (RF-44, RN-24).

Conversa de outra pessoa e tratada como inexistente: quem pede nao fica
sabendo que o identificador existe.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from src.application.dto import MessageDTO
from src.application.services import AccessControl
from src.domain import (
    AuthenticatedUser,
    ChatMessage,
    Conversation,
    ConversationId,
    ConversationRepository,
    MessageId,
    MessageRole,
)

from .chat_with_assistant import ConversationNotFoundError


def load_owned_conversation(
    repository: ConversationRepository,
    access_control: AccessControl,
    user: AuthenticatedUser,
    conversation_id: ConversationId,
) -> Conversation:
    conversation = repository.get_by_id(conversation_id)
    if conversation is None or not access_control.owns_conversation(
        user, conversation.owner_user_id
    ):
        raise ConversationNotFoundError("conversation not found.")
    return conversation


@dataclass(frozen=True, slots=True)
class ConversationRefInput:
    user: AuthenticatedUser
    conversation_id: str


class GetConversationUseCase:
    def __init__(
        self,
        repository: ConversationRepository,
        access_control: AccessControl,
    ) -> None:
        self._repository = repository
        self._access = access_control

    def execute(self, data: ConversationRefInput) -> Conversation:
        return load_owned_conversation(
            self._repository,
            self._access,
            data.user,
            ConversationId(data.conversation_id),
        )


class DeleteConversationUseCase:
    def __init__(
        self,
        repository: ConversationRepository,
        access_control: AccessControl,
    ) -> None:
        self._repository = repository
        self._access = access_control

    def execute(self, data: ConversationRefInput) -> None:
        conversation = load_owned_conversation(
            self._repository,
            self._access,
            data.user,
            ConversationId(data.conversation_id),
        )
        if not self._repository.delete(conversation.id):
            raise ConversationNotFoundError("conversation not found.")


@dataclass(frozen=True, slots=True)
class AddMessageInput:
    user: AuthenticatedUser
    conversation_id: str
    role: str
    content: str


class AddMessageUseCase:
    def __init__(
        self,
        repository: ConversationRepository,
        access_control: AccessControl,
    ) -> None:
        self._repository = repository
        self._access = access_control

    def execute(self, data: AddMessageInput) -> MessageDTO:
        conversation = load_owned_conversation(
            self._repository,
            self._access,
            data.user,
            ConversationId(data.conversation_id),
        )
        saved = self._repository.save_message(
            ChatMessage(
                id=MessageId(str(uuid4())),
                conversation_id=conversation.id,
                role=MessageRole(data.role),
                content=data.content,
            )
        )
        return MessageDTO.from_entity(saved)
