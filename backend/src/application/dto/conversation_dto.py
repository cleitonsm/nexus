from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain import Conversation


@dataclass(frozen=True, slots=True)
class ConversationDTO:
    id: str
    assistant_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int

    @classmethod
    def from_entity(cls, conversation: Conversation) -> "ConversationDTO":
        return cls(
            id=conversation.id.value,
            assistant_id=conversation.assistant_id.value,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=len(conversation.messages),
        )


@dataclass(frozen=True, slots=True)
class RegisterConversationResult:
    conversation: ConversationDTO
