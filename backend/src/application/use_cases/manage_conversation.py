"""Leitura, exclusao e mensagens avulsas de uma conversa (RF-44, RN-24).

Conversa de outra pessoa e tratada como inexistente: quem pede nao fica
sabendo que o identificador existe.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from src.application.dto import MessageDTO
from src.application.services import AccessControl, PersonalDocumentRemover
from src.domain import (
    SUMMARIZER_ASSISTANT_ID,
    AuthenticatedUser,
    ChatMessage,
    Conversation,
    ConversationId,
    Document,
    DomainValidationError,
    ConversationRepository,
    DocumentId,
    DocumentRepository,
    DocumentStatus,
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
        document_repository: DocumentRepository | None = None,
    ) -> None:
        self._repository = repository
        self._access = access_control
        self._documents = document_repository

    def removed_sources(self, conversation: Conversation) -> frozenset[str]:
        """RN-29, D10: documentos citados que foram excluidos ou substituidos.

        As citacoes guardadas continuam na conversa; a tela as marca como
        fonte removida.
        """
        documents = self._documents
        if documents is None:
            return frozenset()
        cited = {
            citation.document_id.value
            for message in conversation.messages
            for citation in message.citations
        }
        return frozenset(
            document_id
            for document_id in cited
            if not _is_available(documents.get_by_id(DocumentId(document_id)))
        )

    def execute(self, data: ConversationRefInput) -> Conversation:
        return load_owned_conversation(
            self._repository,
            self._access,
            data.user,
            ConversationId(data.conversation_id),
        )


def _is_available(document: Document | None) -> bool:
    # SPEC-018: documento pessoal expirado tambem aparece como fonte removida.
    return document is not None and document.status not in (
        DocumentStatus.REPLACED,
        DocumentStatus.EXPIRED,
    )


class DeleteConversationUseCase:
    def __init__(
        self,
        repository: ConversationRepository,
        access_control: AccessControl,
        personal_documents: PersonalDocumentRemover | None = None,
    ) -> None:
        self._repository = repository
        self._access = access_control
        self._personal_documents = personal_documents

    def execute(self, data: ConversationRefInput) -> None:
        conversation = load_owned_conversation(
            self._repository,
            self._access,
            data.user,
            ConversationId(data.conversation_id),
        )
        if (
            self._personal_documents is not None
            and conversation.assistant_id == SUMMARIZER_ASSISTANT_ID
        ):
            # SPEC-018 (RF-120): o documento pessoal sai antes da conversa.
            self._personal_documents.remove_for_conversation(
                conversation.id, actor=data.user
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
        if data.role != MessageRole.USER.value:
            raise DomainValidationError(
                "only messages with role 'user' can be added directly."
            )
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
