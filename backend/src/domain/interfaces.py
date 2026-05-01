from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .entities import Assistant, ChatMessage, Conversation, Document
from .value_objects import (
    AssistantId,
    CollectionName,
    ConversationId,
    DocumentId,
)


class AssistantRepository(Protocol):
    def save(self, assistant: Assistant) -> Assistant: ...

    def list_all(self) -> list[Assistant]: ...

    def get_by_id(self, assistant_id: AssistantId) -> Assistant | None: ...

    def delete(self, assistant_id: AssistantId) -> bool: ...


class DocumentRepository(Protocol):
    def save(self, document: Document) -> Document: ...

    def list_by_assistant(
        self,
        assistant_id: AssistantId,
    ) -> list[Document]: ...


class ConversationRepository(Protocol):
    def save(self, conversation: Conversation) -> Conversation: ...

    def get_by_id(
        self,
        conversation_id: ConversationId,
    ) -> Conversation | None: ...

    def list_by_assistant(
        self,
        assistant_id: AssistantId,
    ) -> list[Conversation]: ...

    def save_message(self, message: ChatMessage) -> ChatMessage: ...

    def list_messages(
        self,
        conversation_id: ConversationId,
    ) -> list[ChatMessage]: ...

    def delete(self, conversation_id: ConversationId) -> bool: ...


class SecretSettingsRepository(Protocol):
    def set_encrypted_value(
        self,
        *,
        key_name: str,
        encrypted_value: str,
    ) -> None: ...

    def get_encrypted_value(self, *, key_name: str) -> str | None: ...


class EmbeddingGateway(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True, slots=True)
class VectorChunk:
    id: str
    document_id: DocumentId
    assistant_id: AssistantId
    chunk_index: int
    source_name: str
    content_hash: str
    text: str
    vector: list[float]


@dataclass(frozen=True, slots=True)
class SearchResult:
    chunk_id: str
    document_id: DocumentId
    score: float
    text: str


class VectorStoreGateway(Protocol):
    def ensure_collection(
        self,
        collection_name: CollectionName,
        vector_size: int,
    ) -> None: ...

    def upsert_chunks(
        self,
        collection_name: CollectionName,
        chunks: list[VectorChunk],
    ) -> None: ...

    def search(
        self,
        collection_name: CollectionName,
        query_vector: list[float],
        limit: int,
    ) -> list[SearchResult]: ...

    def delete_collection(self, collection_name: CollectionName) -> None: ...


class LLMGateway(Protocol):
    def generate(
        self,
        *,
        prompt: str,
        context_chunks: list[str],
        conversation_history: list[ChatMessage],
    ) -> str: ...
