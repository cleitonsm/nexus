from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum

from .citations import Citation
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
    embedding_model: str | None = None
    pipeline_version: str | None = None
    chunk_count: int = 0
    storage_key: str | None = None

    def __post_init__(self) -> None:
        if not self.source_name.strip():
            raise DomainValidationError("document source_name must not be empty.")
        if not self.content_hash.strip():
            raise DomainValidationError("document content_hash must not be empty.")
        if self.chunk_count < 0:
            raise DomainValidationError("document chunk_count must not be negative.")

    @property
    def is_indexed(self) -> bool:
        """Documentos anteriores a SPEC-002 nao registram o modelo."""
        return self.embedding_model is not None

    @property
    def has_original(self) -> bool:
        return self.storage_key is not None

    def is_current(self, *, embedding_model: str, pipeline_version: str) -> bool:
        return (
            self.embedding_model == embedding_model
            and self.pipeline_version == pipeline_version
        )

    def indexed_with(
        self,
        *,
        embedding_model: str,
        pipeline_version: str,
        chunk_count: int,
    ) -> "Document":
        return replace(
            self,
            embedding_model=embedding_model,
            pipeline_version=pipeline_version,
            chunk_count=chunk_count,
        )


@dataclass(frozen=True, slots=True)
class ChatMessage:
    id: MessageId
    conversation_id: ConversationId
    role: MessageRole
    content: str
    created_at: datetime = field(default_factory=_utc_now)
    citations: tuple[Citation, ...] = ()

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise DomainValidationError("chat message content must not be empty.")
        if self.citations and self.role is not MessageRole.ASSISTANT:
            raise DomainValidationError(
                "only assistant messages may carry citations."
            )


@dataclass(frozen=True, slots=True)
class Conversation:
    id: ConversationId
    assistant_id: AssistantId
    name: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    messages: tuple[ChatMessage, ...] = ()
    # Quem criou a conversa (RF-44). Nulo em conversas anteriores a
    # autenticacao, que ficam arquivadas e nao sao exibidas a ninguem.
    owner_user_id: str | None = None

    def append_message(self, message: ChatMessage) -> "Conversation":
        if message.conversation_id != self.id:
            raise DomainValidationError(
                "message conversation_id does not match conversation id."
            )
        return Conversation(
            id=self.id,
            assistant_id=self.assistant_id,
            name=self.name,
            created_at=self.created_at,
            updated_at=message.created_at,
            messages=(*self.messages, message),
            owner_user_id=self.owner_user_id,
        )


class ReindexStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ReindexJob:
    """Andamento de uma reindexacao; ha no maximo uma em curso por assistente."""

    id: str
    assistant_id: AssistantId
    target_collection: str
    status: ReindexStatus = ReindexStatus.RUNNING
    total_documents: int = 0
    processed_documents: int = 0
    error: str | None = None
    started_at: datetime = field(default_factory=_utc_now)
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise DomainValidationError("reindex job id must not be empty.")
        if not self.target_collection.strip():
            raise DomainValidationError(
                "reindex job target_collection must not be empty."
            )
        if self.total_documents < 0 or self.processed_documents < 0:
            raise DomainValidationError(
                "reindex job document counters must not be negative."
            )

    @property
    def is_running(self) -> bool:
        return self.status is ReindexStatus.RUNNING

    def with_progress(self, *, total: int, processed: int) -> "ReindexJob":
        return replace(self, total_documents=total, processed_documents=processed)

    def succeed(self) -> "ReindexJob":
        return replace(
            self,
            status=ReindexStatus.SUCCEEDED,
            error=None,
            finished_at=_utc_now(),
        )

    def fail(self, error: str) -> "ReindexJob":
        return replace(
            self,
            status=ReindexStatus.FAILED,
            error=error.strip() or "unknown error",
            finished_at=_utc_now(),
        )
