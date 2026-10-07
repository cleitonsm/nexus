from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .chunking import DocumentChunk, ExtractedDocument
from .entities import (
    Assistant,
    ChatMessage,
    Conversation,
    Document,
    ReindexJob,
)
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

    def delete(self, document_id: DocumentId) -> bool: ...


class ReindexJobRepository(Protocol):
    def save(self, job: ReindexJob) -> ReindexJob: ...

    def get_by_id(self, job_id: str) -> ReindexJob | None: ...

    def get_latest(self, assistant_id: AssistantId) -> ReindexJob | None: ...

    def get_running(self, assistant_id: AssistantId) -> ReindexJob | None: ...

    def list_running(self) -> list[ReindexJob]: ...


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
    """Vetoriza localmente; documentos e consultas tem entradas distintas."""

    @property
    def model_name(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


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
    section_path: str = ""
    page: int | None = None
    embedding_model: str = ""
    pipeline_version: str = ""


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

    def collection_exists(self, collection_name: CollectionName) -> bool:
        """Indica se existe uma collection fisica com esse nome (nao um alias)."""
        ...

    def count_points(self, collection_name: CollectionName) -> int: ...

    def resolve_alias(self, alias: CollectionName) -> CollectionName | None:
        """Collection para a qual o alias aponta, ou None se nao existir."""
        ...

    def point_alias(
        self,
        alias: CollectionName,
        collection_name: CollectionName,
    ) -> None:
        """Cria o alias ou o troca de forma atomica."""
        ...


class TokenCounter(Protocol):
    """Mede textos com o tokenizador do modelo de embedding."""

    @property
    def max_tokens(self) -> int:
        """Limite de sequencia do modelo, incluidos os tokens especiais."""
        ...

    def count(self, text: str) -> int:
        """Tokens que o modelo consome para o texto, incluidos os especiais."""
        ...


class DocumentChunker(Protocol):
    def chunk(self, document: ExtractedDocument) -> list[DocumentChunk]: ...


class DocumentExtractor(Protocol):
    """Converte o arquivo enviado em blocos; ValueError para arquivo invalido."""

    def extract(
        self,
        *,
        filename: str | None,
        content_type: str | None,
        raw_content: bytes,
    ) -> ExtractedDocument: ...


class DocumentFileStorage(Protocol):
    """Guarda o arquivo original para reprocessamento."""

    def save(
        self,
        *,
        assistant_id: AssistantId,
        document_id: DocumentId,
        filename: str,
        content: bytes,
    ) -> str:
        """Grava o arquivo e devolve a chave de armazenamento."""
        ...

    def load(self, storage_key: str) -> bytes: ...


class LLMGateway(Protocol):
    def generate(
        self,
        *,
        prompt: str,
        context_chunks: list[str],
        conversation_history: list[ChatMessage],
    ) -> str: ...


class AnswerJudge(Protocol):
    """Julga se uma resposta e sustentada pelo contexto recuperado."""

    def is_faithful(
        self,
        *,
        question: str,
        answer: str,
        context_chunks: list[str],
    ) -> bool: ...
