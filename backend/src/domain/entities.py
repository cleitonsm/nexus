from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from .citations import Citation
from .document_summary import PersonalScope, SummaryStage
from .errors import DomainValidationError, InvalidDocumentStateError
from .llm_settings import validate_model_name
from .retrieval_profile import RetrievalProfile
from .value_objects import (
    AssistantId,
    AssistantName,
    ConversationId,
    DocumentId,
    DocumentMetadata,
    LLMCredentialId,
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
    # SPEC-013: sem credencial, segue a padrao do sistema (RN-40). Seguindo a
    # padrao, o modelo escolhido tem recuo para o modelo padrao dela quando a
    # padrao nova nao o tem (D11). Perfil vazio = padrao global (RN-41).
    llm_credential_id: LLMCredentialId | None = None
    llm_model: str | None = None
    retrieval_profile: RetrievalProfile = field(default_factory=RetrievalProfile)
    # SPEC-018 (ADR 0014): assistente criado pela migracao, visivel a todo
    # papel e sem exclusao nem edicao de perfil (RN-55). None nos comuns.
    system_kind: str | None = None

    def __post_init__(self) -> None:
        if self.system_kind is not None and not self.system_kind.strip():
            raise DomainValidationError("assistant system_kind must not be blank.")
        if self.llm_model is not None:
            object.__setattr__(self, "llm_model", validate_model_name(self.llm_model))
        if self.description is not None and not self.description.strip():
            raise DomainValidationError(
                "assistant description must not be empty when provided."
            )
        if self.initial_prompt is not None and not self.initial_prompt.strip():
            raise DomainValidationError(
                "assistant initial_prompt must not be empty when provided."
            )

    @property
    def is_system(self) -> bool:
        return self.system_kind is not None


class DocumentStatus(StrEnum):
    """Ciclo de vida do documento (SPEC-005)."""

    PENDING = "pendente"
    PROCESSING = "processando"
    INDEXED = "indexado"
    FAILED = "falhou"
    # Versao anterior de um documento substituido (D5): sem trechos nem
    # arquivo; o registro fica para identificar citacoes antigas (RN-29).
    REPLACED = "substituido"
    # SPEC-018: documento pessoal apagado (conversa excluida ou 30 dias, D9).
    # Fica como lapide sem conteudo: sustenta a cota e a auditoria (T7).
    EXPIRED = "expirado"


_DOCUMENT_TRANSITIONS: dict[DocumentStatus, frozenset[DocumentStatus]] = {
    DocumentStatus.PENDING: frozenset(
        {DocumentStatus.PROCESSING, DocumentStatus.EXPIRED}
    ),
    DocumentStatus.PROCESSING: frozenset(
        {
            DocumentStatus.INDEXED,
            DocumentStatus.PENDING,
            DocumentStatus.FAILED,
            DocumentStatus.EXPIRED,
        }
    ),
    DocumentStatus.INDEXED: frozenset(
        {DocumentStatus.REPLACED, DocumentStatus.EXPIRED}
    ),
    DocumentStatus.FAILED: frozenset(
        {DocumentStatus.PENDING, DocumentStatus.EXPIRED}
    ),
    DocumentStatus.REPLACED: frozenset(),
    DocumentStatus.EXPIRED: frozenset(),
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
    # SPEC-018 (RN-58): documento pessoal do resumidor. Conversa so com dono;
    # a lapide perde a conversa e mantem o dono (T7). None na base.
    owner_user_id: str | None = None
    conversation_id: ConversationId | None = None
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.owner_user_id is not None:
            owner = self.owner_user_id.strip()
            if not owner:
                raise DomainValidationError("document owner_user_id must not be blank.")
            object.__setattr__(self, "owner_user_id", owner)
        if self.conversation_id is not None and self.owner_user_id is None:
            raise DomainValidationError(
                "a document bound to a conversation must have an owner."
            )
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

    @property
    def is_personal(self) -> bool:
        """SPEC-018: documento do usuario enviado ao resumidor (RN-58)."""
        return self.owner_user_id is not None

    @property
    def personal_scope(self) -> PersonalScope | None:
        """Escopo da busca no documento pessoal (RN-59); None na base e na lapide."""
        if self.owner_user_id is None or self.conversation_id is None:
            return None
        return PersonalScope(
            owner_user_id=self.owner_user_id, conversation_id=self.conversation_id
        )

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

    def mark_expired(self) -> "Document":
        """SPEC-018 (RF-120, D9): lapide sem trechos nem original."""
        if not self.is_personal:
            raise InvalidDocumentStateError("only personal documents can expire.")
        return self._move_to(DocumentStatus.EXPIRED, chunk_count=0, storage_key=None)

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
    # autenticacao: ficam arquivadas, fora das listas dos usuarios; so o
    # administrador as lista, le e exclui (decisao PC-D5).
    owner_user_id: str | None = None
    # Preenchido nas listagens, que nao carregam as mensagens (fix-8).
    message_total: int | None = None

    @property
    def message_count(self) -> int:
        if self.message_total is not None:
            return self.message_total
        return len(self.messages)

    @property
    def is_archived(self) -> bool:
        return self.owner_user_id is None

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
    # SPEC-018 (D21): resumo hierarquico do documento pessoal, depois da
    # indexacao, na mesma fila (ADR 0009).
    SUMMARIZE = "resumo"


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


@dataclass(frozen=True, slots=True)
class DocumentSummarySection:
    """Mini-resumo de um lote de secoes (SPEC-018, RN-63, D30)."""

    document_id: DocumentId
    position: int
    title: str
    input_tokens: int
    content: str
    page_start: int | None = None

    def __post_init__(self) -> None:
        if self.position < 0:
            raise DomainValidationError("summary section position must not be negative.")
        if self.input_tokens < 0:
            raise DomainValidationError("summary section tokens must not be negative.")
        if not self.content.strip():
            raise DomainValidationError("summary section content must not be empty.")
        if self.page_start is not None and self.page_start < 1:
            raise DomainValidationError("summary section page must be at least 1.")


@dataclass(frozen=True, slots=True)
class DocumentSummary:
    """Andamento e resultado do resumo de um documento pessoal (RN-62 a RN-64)."""

    document_id: DocumentId
    stage: SummaryStage = SummaryStage.UPLOADED
    batches_done: int = 0
    batches_total: int = 0
    content: str | None = None
    citations: tuple[Citation, ...] = ()
    document_tokens: int | None = None
    prompt_version: str | None = None
    model: str | None = None
    failure_code: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "citations", tuple(self.citations))
        if self.batches_done < 0 or self.batches_total < 0:
            raise DomainValidationError("summary batches must not be negative.")
        if self.batches_done > self.batches_total:
            raise DomainValidationError("summary batches done must not pass total.")
        if self.document_tokens is not None and self.document_tokens < 0:
            raise DomainValidationError("summary document tokens must not be negative.")
        if self.stage is SummaryStage.READY and not (self.content or "").strip():
            raise DomainValidationError("a ready summary must have content.")
        if self.stage is SummaryStage.FAILED and not (self.failure_code or "").strip():
            raise DomainValidationError("a failed summary must have a failure code.")
