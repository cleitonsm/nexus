from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from .citations import Citation
from .errors import DomainValidationError, InvalidDocumentStateError
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


class DocumentStatus(StrEnum):
    """Ciclo de vida do documento (SPEC-005)."""

    PENDING = "pendente"
    PROCESSING = "processando"
    INDEXED = "indexado"
    FAILED = "falhou"
    # Versao anterior de um documento substituido (D5): sem trechos nem
    # arquivo; o registro fica para identificar citacoes antigas (RN-29).
    REPLACED = "substituido"


_DOCUMENT_TRANSITIONS: dict[DocumentStatus, frozenset[DocumentStatus]] = {
    DocumentStatus.PENDING: frozenset({DocumentStatus.PROCESSING}),
    DocumentStatus.PROCESSING: frozenset(
        {DocumentStatus.INDEXED, DocumentStatus.PENDING, DocumentStatus.FAILED}
    ),
    DocumentStatus.INDEXED: frozenset({DocumentStatus.REPLACED}),
    DocumentStatus.FAILED: frozenset({DocumentStatus.PENDING}),
    DocumentStatus.REPLACED: frozenset(),
}


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
    # Documentos anteriores a SPEC-005 ja estavam indexados ao serem gravados.
    status: DocumentStatus = DocumentStatus.INDEXED
    failure_reason: str | None = None
    attempts: int = 0
    size_bytes: int | None = None
    version: int = 1
    replaces_document_id: DocumentId | None = None
    uploaded_by: str | None = None

    def __post_init__(self) -> None:
        if not self.source_name.strip():
            raise DomainValidationError("document source_name must not be empty.")
        if not self.content_hash.strip():
            raise DomainValidationError("document content_hash must not be empty.")
        if self.chunk_count < 0:
            raise DomainValidationError("document chunk_count must not be negative.")
        if self.attempts < 0:
            raise DomainValidationError("document attempts must not be negative.")
        if self.version < 1:
            raise DomainValidationError("document version must be at least 1.")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise DomainValidationError("document size_bytes must not be negative.")
        if self.replaces_document_id == self.id:
            raise DomainValidationError("a document cannot replace itself.")

    @property
    def is_indexed(self) -> bool:
        """Documentos anteriores a SPEC-002 nao registram o modelo."""
        return self.embedding_model is not None

    @property
    def has_original(self) -> bool:
        return self.storage_key is not None

    @property
    def is_searchable(self) -> bool:
        """RN-27: so documentos indexados participam das buscas."""
        return self.status is DocumentStatus.INDEXED

    @property
    def is_in_progress(self) -> bool:
        return self.status in (DocumentStatus.PENDING, DocumentStatus.PROCESSING)

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

    def start_processing(self, attempt: int) -> "Document":
        """O worker reservou o job; ``attempt`` conta a partir de 1."""
        if attempt < 1:
            raise DomainValidationError("processing attempt must be at least 1.")
        return self._move_to(DocumentStatus.PROCESSING, attempts=attempt)

    def mark_indexed(
        self,
        *,
        embedding_model: str,
        pipeline_version: str,
        chunk_count: int,
    ) -> "Document":
        return self._move_to(
            DocumentStatus.INDEXED,
            failure_reason=None,
            embedding_model=embedding_model,
            pipeline_version=pipeline_version,
            chunk_count=chunk_count,
        )

    def retry_later(self) -> "Document":
        """Falha transitoria: volta a fila para nova tentativa (RF-55)."""
        return self._move_to(DocumentStatus.PENDING)

    def mark_failed(self, reason: str) -> "Document":
        if not reason.strip():
            raise DomainValidationError("failure reason must not be empty.")
        return self._move_to(
            DocumentStatus.FAILED,
            failure_reason=reason.strip(),
            chunk_count=0,
        )

    def request_processing(self) -> "Document":
        """Reprocessamento a partir do original guardado (RF-54)."""
        if not self.has_original:
            raise InvalidDocumentStateError(
                "document has no stored original file to reprocess."
            )
        return self._move_to(
            DocumentStatus.PENDING,
            failure_reason=None,
            attempts=0,
        )

    def mark_replaced(self) -> "Document":
        return self._move_to(DocumentStatus.REPLACED, chunk_count=0)

    def _move_to(self, target: DocumentStatus, **changes: object) -> "Document":
        if target not in _DOCUMENT_TRANSITIONS[self.status]:
            raise InvalidDocumentStateError(
                f"document cannot go from {self.status.value} to {target.value}."
            )
        return replace(self, status=target, **changes)  # type: ignore[arg-type]


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
    """Andamento de uma reindexacao; ha no maximo uma em curso por assistente.

    PC-D4: o worker reserva o job (``claim``) por um prazo renovado a cada
    documento (``renew``). Prazo vencido com o job ainda em curso indica worker
    interrompido: o job volta a poder ser reservado, ate o limite de tentativas.
    """

    id: str
    assistant_id: AssistantId
    target_collection: str
    status: ReindexStatus = ReindexStatus.RUNNING
    total_documents: int = 0
    processed_documents: int = 0
    error: str | None = None
    started_at: datetime = field(default_factory=_utc_now)
    finished_at: datetime | None = None
    attempts: int = 0
    lease_expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise DomainValidationError("reindex job id must not be empty.")
        if self.attempts < 0:
            raise DomainValidationError("reindex job attempts must not be negative.")
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

    def is_claimable(self, now: datetime) -> bool:
        """Em curso e sem worker com prazo valido."""
        return self.is_running and (
            self.lease_expires_at is None or self.lease_expires_at <= now
        )

    def claim(self, now: datetime, lease: timedelta) -> "ReindexJob":
        if not self.is_claimable(now):
            raise DomainValidationError("reindex job is not available to claim.")
        return replace(self, attempts=self.attempts + 1, lease_expires_at=now + lease)

    def renew(self, now: datetime, lease: timedelta) -> "ReindexJob":
        return replace(self, lease_expires_at=now + lease)

    def with_progress(self, *, total: int, processed: int) -> "ReindexJob":
        return replace(self, total_documents=total, processed_documents=processed)

    def succeed(self) -> "ReindexJob":
        return replace(
            self,
            status=ReindexStatus.SUCCEEDED,
            error=None,
            finished_at=_utc_now(),
            lease_expires_at=None,
        )

    def fail(self, error: str) -> "ReindexJob":
        return replace(
            self,
            status=ReindexStatus.FAILED,
            error=error.strip() or "unknown error",
            finished_at=_utc_now(),
            lease_expires_at=None,
        )


class IngestionJobKind(StrEnum):
    INGEST = "ingestao"
    REPROCESS = "reprocessamento"


class IngestionJobStatus(StrEnum):
    PENDING = "pendente"
    PROCESSING = "processando"
    DONE = "concluido"
    FAILED = "falhou"


@dataclass(frozen=True, slots=True)
class IngestionJob:
    """Pedido de processamento de um documento, consumido pelo worker (RF-48)."""

    id: str
    document_id: DocumentId
    kind: IngestionJobKind = IngestionJobKind.INGEST
    status: IngestionJobStatus = IngestionJobStatus.PENDING
    attempts: int = 0
    available_at: datetime = field(default_factory=_utc_now)
    reserved_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise DomainValidationError("ingestion job id must not be empty.")
        if self.attempts < 0:
            raise DomainValidationError("ingestion job attempts must not be negative.")

    def reserve(self, now: datetime) -> "IngestionJob":
        if self.status is not IngestionJobStatus.PENDING:
            raise DomainValidationError("only pending jobs can be reserved.")
        return replace(
            self,
            status=IngestionJobStatus.PROCESSING,
            attempts=self.attempts + 1,
            reserved_at=now,
        )

    def complete(self) -> "IngestionJob":
        return replace(self, status=IngestionJobStatus.DONE, last_error=None)

    def retry_at(self, available_at: datetime, error: str) -> "IngestionJob":
        return replace(
            self,
            status=IngestionJobStatus.PENDING,
            available_at=available_at,
            reserved_at=None,
            last_error=error.strip() or "unknown error",
        )

    def fail(self, error: str) -> "IngestionJob":
        return replace(
            self,
            status=IngestionJobStatus.FAILED,
            last_error=error.strip() or "unknown error",
        )
