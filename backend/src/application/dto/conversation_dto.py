from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain import ChatMessage, Conversation


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


@dataclass(frozen=True, slots=True)
class ListConversationsResult:
    conversations: list[ConversationDTO]


@dataclass(frozen=True, slots=True)
class MessageDTO:
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime

    @classmethod
    def from_entity(cls, message: ChatMessage) -> "MessageDTO":
        return cls(
            id=message.id.value,
            conversation_id=message.conversation_id.value,
            role=message.role.value,
            content=message.content,
            created_at=message.created_at,
        )


@dataclass(frozen=True, slots=True)
class ChatTurnResult:
    conversation_id: str
    assistant_id: str
    user_message: MessageDTO
    assistant_message: MessageDTO
    used_context_chunks: int
    fallback_used: bool
