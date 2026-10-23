from __future__ import annotations

from dataclasses import dataclass

from src.application.dto import ConversationDTO, ListConversationsResult
from src.application.services import AccessControl
from src.domain import AssistantId, AuthenticatedUser, ConversationRepository


@dataclass(frozen=True, slots=True)
class ListConversationsInput:
    user: AuthenticatedUser
    assistant_id: str


class ListConversationsUseCase:
    """RN-24: lista apenas as conversas do proprio usuario."""

    def __init__(
        self,
        repository: ConversationRepository,
        access_control: AccessControl,
    ) -> None:
        self._repository = repository
        self._access = access_control

    def execute(self, data: ListConversationsInput) -> ListConversationsResult:
        assistant_id = AssistantId(data.assistant_id)
        self._access.require_assistant_access(
            data.user, assistant_id, "conversation.list"
        )
        conversations = self._repository.list_by_assistant(
            assistant_id,
            owner_user_id=data.user.id,
        )
        return ListConversationsResult(
            conversations=[
                ConversationDTO.from_entity(conversation)
                for conversation in conversations
            ]
        )
