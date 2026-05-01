from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from .errors import DomainValidationError
from .value_objects import (
    AssistantId,
    AssistantName,
    ConversationId,
    DocumentId,
    DocumentMetadata,
    MessageId,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class Assistant:
    id: AssistantId
    name: AssistantName
    description: str | None = None
    initial_prompt: str | None = None
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if self.description is not None and not self.description.strip():
            raise DomainValidationError(
                "assistant description must not be empty when provided."
            )
        if self.initial_prompt is not None and not self.initial_prompt.strip():
            raise DomainValidationError(
                "assistant initial_prompt must not be empty when provided."
            )


@dataclass(frozen=True, slots=True)
class Document:
    id: DocumentId
    assistant_id: AssistantId
    source_name: str
    content_hash: str
    metadata: DocumentMetadata = field(
        default_factory=lambda: DocumentMetadata(values={})
    )
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.source_name.strip():
            raise DomainValidationError("document source_name must not be empty.")
        if not self.content_hash.strip():
            raise DomainValidationError("document content_hash must not be empty.")


@dataclass(frozen=True, slots=True)
class ChatMessage:
    id: MessageId
    conversation_id: ConversationId
    role: MessageRole
    content: str
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise DomainValidationError("chat message content must not be empty.")


@dataclass(frozen=True, slots=True)
class Conversation:
    id: ConversationId
    assistant_id: AssistantId
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    messages: tuple[ChatMessage, ...] = ()

    def append_message(self, message: ChatMessage) -> "Conversation":
        if message.conversation_id != self.id:
            raise DomainValidationError(
                "message conversation_id does not match conversation id."
            )
        return Conversation(
            id=self.id,
            assistant_id=self.assistant_id,
            created_at=self.created_at,
            updated_at=message.created_at,
            messages=(*self.messages, message),
        )
