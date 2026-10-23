from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from src.application.dto import ConversationDTO, RegisterConversationResult
from src.application.services import AccessControl
from src.domain import (
    AssistantId,
    AuthenticatedUser,
    Conversation,
    ConversationId,
    ConversationRepository,
)


@dataclass(frozen=True, slots=True)
class RegisterConversationInput:
    user: AuthenticatedUser
    assistant_id: str
    conversation_id: str | None = None


class RegisterConversationUseCase:
    """RF-44: a conversa nasce associada a quem a criou."""

    def __init__(
        self,
        repository: ConversationRepository,
        access_control: AccessControl,
    ) -> None:
        self._repository = repository
        self._access = access_control

    def execute(self, data: RegisterConversationInput) -> RegisterConversationResult:
        assistant_id = AssistantId(data.assistant_id)
        self._access.require_assistant_access(
            data.user, assistant_id, "conversation.create"
        )
        conversation = Conversation(
            id=ConversationId(data.conversation_id or str(uuid4())),
            assistant_id=assistant_id,
            owner_user_id=data.user.id,
        )
        saved = self._repository.save(conversation)
        return RegisterConversationResult(conversation=ConversationDTO.from_entity(saved))
