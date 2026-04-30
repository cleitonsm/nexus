from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from src.application.dto import ConversationDTO, RegisterConversationResult
from src.domain import AssistantId, Conversation, ConversationId, ConversationRepository


@dataclass(frozen=True, slots=True)
class RegisterConversationInput:
    assistant_id: str
    conversation_id: str | None = None


class RegisterConversationUseCase:
    def __init__(self, repository: ConversationRepository) -> None:
        self._repository = repository

    def execute(self, data: RegisterConversationInput) -> RegisterConversationResult:
        conversation = Conversation(
            id=ConversationId(data.conversation_id or str(uuid4())),
            assistant_id=AssistantId(data.assistant_id),
        )
        saved = self._repository.save(conversation)
        return RegisterConversationResult(conversation=ConversationDTO.from_entity(saved))
