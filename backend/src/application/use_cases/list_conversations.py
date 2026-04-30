from __future__ import annotations

from dataclasses import dataclass

from src.application.dto import ConversationDTO, ListConversationsResult
from src.domain import AssistantId, ConversationRepository


@dataclass(frozen=True, slots=True)
class ListConversationsInput:
    assistant_id: str


class ListConversationsUseCase:
    def __init__(self, repository: ConversationRepository) -> None:
        self._repository = repository

    def execute(self, data: ListConversationsInput) -> ListConversationsResult:
        assistant_id = AssistantId(data.assistant_id)
        conversations = self._repository.list_by_assistant(assistant_id)
        return ListConversationsResult(
            conversations=[
                ConversationDTO.from_entity(conversation)
                for conversation in conversations
            ]
        )
