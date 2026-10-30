"""SPEC-018: documento pessoal do resumidor (RF-114 a RF-120).

O envio so valida, guarda o original e enfileira, como a ingestao da base
(ADR 0009): extracao, contagem, indexacao e resumo ficam com o worker.
Conversa de outra pessoa e tratada como inexistente (RN-24, RN-58).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from uuid import uuid4

from src.application.dto import StoredSummaryDTO, SummarizerInfoDTO, SummaryDocumentDTO
from src.application.services import (
    AccessControl,
    DocumentIndexer,
    PersonalDocumentRemover,
)
from src.application.services.document_indexing import hash_content
from src.application.services.ingestion import WORKER_USER
from src.domain import (
    DAILY_SUMMARY_DOCUMENTS,
    DAILY_SUMMARY_WINDOW,
    SUMMARIZER_ASSISTANT_ID,
    AccessPolicy,
    AuditAction,
    AuditResource,
    AuthenticatedUser,
    Conversation,
    ConversationDocumentExistsError,
    ConversationId,
    ConversationRepository,
    Document,
    DocumentFileStorage,
    DocumentId,
    DocumentRepository,
    DocumentStatus,
    DocumentSummary,
    DocumentSummaryRepository,
    IngestionJob,
    IngestionJobKind,
    IngestionJobQueue,
    NotSummarizerConversationError,
    SummarizerCapabilities,
    SummaryDailyLimitError,
    SummaryNotFailedError,
    SummaryNotReadyError,
    SummaryStage,
    daily_summary_limit_reached,
    summary_document_expires_at,
    summary_progress,
)

from .ingest_document import SUPPORTED_DOCUMENT_FORMATS, DocumentTooLargeError
from .chat_with_assistant import ConversationNotFoundError
from .manage_conversation import load_owned_conversation

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SummaryDocumentNotFoundError(Exception):
    """A conversa nao tem documento pessoal (404)."""


class UnsupportedDocumentFormatError(ValueError):
    """Formato fora da lista da ingestao (415, D17)."""


def summarizer_capabilities(max_file_bytes: int) -> SummarizerCapabilities:
    """D16 e D17: tamanho e formatos vem da ingestao; o resto, do dominio."""
    return SummarizerCapabilities(formats=SUPPORTED_DOCUMENT_FORMATS, max_bytes=max_file_bytes)


class GetSummarizerInfoUseCase:
    """RF-119: finalidade e especificacoes, sem LLM (D37, RNF-38)."""

    def __init__(self, *, max_file_bytes: int) -> None:
        self._capabilities = summarizer_capabilities(max_file_bytes)

    def execute(self, user: AuthenticatedUser) -> SummarizerInfoDTO:
        del user  # autenticado pela rota; o texto e o mesmo para todos
        return SummarizerInfoDTO.from_capabilities(
            SUMMARIZER_ASSISTANT_ID.value, self._capabilities
        )


def _summarizer_conversation(
    conversations: ConversationRepository,
    access: AccessControl,
    user: AuthenticatedUser,
    conversation_id: str,
) -> Conversation:
    conversation = load_owned_conversation(
        conversations, access, user, ConversationId(conversation_id)
    )
    # RN-58: dono da conversa e com papel no Nexus (AccessPolicy).
    if not AccessPolicy.can_use_personal_document(user, conversation.owner_user_id):
        raise ConversationNotFoundError("conversation not found.")
    if conversation.assistant_id != SUMMARIZER_ASSISTANT_ID:
        raise NotSummarizerConversationError(
            "personal documents belong to summarizer conversations."
        )
    return conversation


@dataclass(frozen=True, slots=True)
class UploadSummaryDocumentInput:
    user: AuthenticatedUser
    conversation_id: str
    source_name: str
    raw_content: bytes
    content_type: str | None = None


class UploadSummaryDocumentUseCase:
    """RF-114 e RF-115: um documento por conversa, na cota do dia (RN-58, RN-60)."""

    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        documents: DocumentRepository,
        summaries: DocumentSummaryRepository,
        document_indexer: DocumentIndexer,
        file_storage: DocumentFileStorage,
        job_queue: IngestionJobQueue,
        access_control: AccessControl,
        max_file_bytes: int,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be positive.")
        self._conversations = conversations
        self._documents = documents
        self._summaries = summaries
        self._indexer = document_indexer
        self._storage = file_storage
        self._queue = job_queue
        self._access = access_control
        self._max_file_bytes = max_file_bytes
        self._clock = clock

    def execute(self, data: UploadSummaryDocumentInput) -> SummaryDocumentDTO:
        conversation = _summarizer_conversation(
            self._conversations, self._access, data.user, data.conversation_id
        )
        self._access.require_assistant_access(
            data.user, SUMMARIZER_ASSISTANT_ID, AuditAction.SUMMARY_DOCUMENT_UPLOADED
        )
        if self._documents.get_personal_by_conversation(conversation.id) is not None:
            raise ConversationDocumentExistsError("the conversation already has a document.")
        self._validate(data)
        now = self._clock()
        sent = self._documents.count_personal_since(data.user.id, now - DAILY_SUMMARY_WINDOW)
        if daily_summary_limit_reached(sent):
            raise SummaryDailyLimitError(
                f"daily limit of {DAILY_SUMMARY_DOCUMENTS} documents reached.",
                limit=DAILY_SUMMARY_DOCUMENTS,
            )
        document_id = DocumentId(str(uuid4()))
        storage_key = self._storage.save(
            assistant_id=SUMMARIZER_ASSISTANT_ID,
            document_id=document_id,
            filename=data.source_name,
            content=data.raw_content,
        )
        try:
            document = self._documents.save(
                Document(
                    id=document_id,
                    assistant_id=SUMMARIZER_ASSISTANT_ID,
                    source_name=data.source_name,
                    content_hash=hash_content(data.raw_content),
                    status=DocumentStatus.PENDING,
                    storage_key=storage_key,
                    size_bytes=len(data.raw_content),
                    uploaded_by=data.user.id,
                    owner_user_id=data.user.id,
                    conversation_id=conversation.id,
                    expires_at=summary_document_expires_at(now),
                    created_at=now,
                )
            )
        except Exception:
            self._discard_file(storage_key)
            raise
        try:
            summary = self._summaries.create(
                DocumentSummary(document_id=document.id, created_at=now, updated_at=now)
            )
            self._queue.enqueue(IngestionJob(id=str(uuid4()), document_id=document.id))
        except Exception:
            # Sem job o documento ficaria "enviado" para sempre.
            self._documents.delete(document.id)
            self._discard_file(storage_key)
            raise
        self._access.audit(
            data.user,
            AuditAction.SUMMARY_DOCUMENT_UPLOADED,
            resource_type=AuditResource.DOCUMENT,
            resource_id=document.id.value,
            details={
                "conversation_id": conversation.id.value,
                "source_name": document.source_name,
                "size_bytes": document.size_bytes,
                "content_hash": document.content_hash,
                "format": PurePosixPath(document.source_name).suffix.lower(),
            },
        )
        return SummaryDocumentDTO.build(document, summary_progress(document, summary))

    def _validate(self, data: UploadSummaryDocumentInput) -> None:
        if len(data.raw_content) > self._max_file_bytes:
            raise DocumentTooLargeError(
                f"file exceeds the limit of {self._max_file_bytes} bytes."
            )
        if not data.raw_content:
            raise ValueError("uploaded file is empty.")
        supported = self._indexer.supports(
            source_name=data.source_name, content_type=data.content_type
        ) and self._indexer.supports(source_name=data.source_name, content_type=None)
        if not supported:
            raise UnsupportedDocumentFormatError(
                "unsupported file format. Supported formats: "
                + ", ".join(SUPPORTED_DOCUMENT_FORMATS)
            )

    def _discard_file(self, storage_key: str) -> None:
        try:
            self._storage.delete(storage_key)
        except Exception:  # noqa: BLE001 - o erro original e o relevante
            logger.exception(
                "summary_document.original.discard_failed",
                extra={"storage_key": storage_key},
            )


@dataclass(frozen=True, slots=True)
class SummaryConversationInput:
    user: AuthenticatedUser
    conversation_id: str


class _ConversationDocument:
    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        documents: DocumentRepository,
        summaries: DocumentSummaryRepository,
        access_control: AccessControl,
    ) -> None:
        self._conversations = conversations
        self._documents = documents
        self._summaries = summaries
        self._access = access_control

    def _load(self, data: SummaryConversationInput) -> tuple[Document, DocumentSummary | None]:
        conversation = _summarizer_conversation(
            self._conversations, self._access, data.user, data.conversation_id
        )
        document = self._documents.get_personal_by_conversation(conversation.id)
        if document is None:
            raise SummaryDocumentNotFoundError("the conversation has no document.")
        return document, self._summaries.get(document.id)


class GetSummaryDocumentStatusUseCase(_ConversationDocument):
    """RF-115 e D36."""

    def execute(self, data: SummaryConversationInput) -> SummaryDocumentDTO:
        document, summary = self._load(data)
        return SummaryDocumentDTO.build(document, summary_progress(document, summary))


class GetStoredSummaryUseCase(_ConversationDocument):
    """RF-117 e RNF-37: le o banco, sem LLM."""

    def execute(self, data: SummaryConversationInput) -> StoredSummaryDTO:
        document, summary = self._load(data)
        if (
            document.status is DocumentStatus.EXPIRED
            or summary is None
            or summary.stage is not SummaryStage.READY
        ):
            raise SummaryNotReadyError("the summary is not ready.")
        return StoredSummaryDTO.from_entity(summary)


class RetrySummaryUseCase(_ConversationDocument):
    """RN-64: refaz so o resumo, sem reindexar e sem nova cota."""

    def __init__(self, *, job_queue: IngestionJobQueue, **kwargs) -> None:
        super().__init__(**kwargs)
        self._queue = job_queue

    def execute(self, data: SummaryConversationInput) -> SummaryDocumentDTO:
        document, summary = self._load(data)
        if (
            document.status is not DocumentStatus.INDEXED
            or summary is None
            or summary.stage is not SummaryStage.FAILED
        ):
            raise SummaryNotFailedError("only a failed summary can be retried.")
        self._summaries.set_stage(document.id, SummaryStage.SUMMARIZING)
        self._queue.enqueue(
            IngestionJob(id=str(uuid4()), document_id=document.id, kind=IngestionJobKind.SUMMARIZE)
        )
        return SummaryDocumentDTO.build(
            document, summary_progress(document, self._summaries.get(document.id))
        )


class PurgeExpiredSummaryDocumentsUseCase:
    """RF-120 e T9: apaga os vencidos; falha num documento nao para os outros."""

    def __init__(
        self,
        *,
        documents: DocumentRepository,
        remover: PersonalDocumentRemover,
        clock: Callable[[], datetime] = _utc_now,
        batch_size: int = 100,
    ) -> None:
        self._documents = documents
        self._remover = remover
        self._clock = clock
        self._batch_size = batch_size

    def execute(self) -> int:
        removed = 0
        for document in self._documents.list_personal_to_expire(self._clock(), self._batch_size):
            try:
                self._remover.remove(document, reason="expired", actor=WORKER_USER)
                removed += 1
            except Exception:  # noqa: BLE001 - fica para a proxima rodada
                logger.exception(
                    "summary_document.expire_failed",
                    extra={"document_id": document.id.value},
                )
        return removed
