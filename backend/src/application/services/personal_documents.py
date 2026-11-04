"""SPEC-018: remocao do documento pessoal do resumidor (RF-120, D9 a D11, T9).

Usada na exclusao da conversa e na limpeza dos vencidos. Cada passo e
idempotente: uma falha no meio deixa o documento para a proxima rodada da
limpeza, sem apagar o que ja foi apagado de novo.
"""

from __future__ import annotations

import logging
from typing import Literal

from src.domain import (
    SUMMARIZER_COLLECTION,
    AuditAction,
    AuditResource,
    AuthenticatedUser,
    ConversationId,
    Document,
    DocumentFileStorage,
    DocumentRepository,
    DocumentStatus,
    DocumentSummaryRepository,
    VectorStoreGateway,
)

from .access_control import AccessControl

logger = logging.getLogger(__name__)

RemovalReason = Literal["conversation_deleted", "expired"]


class PersonalDocumentRemover:
    def __init__(
        self,
        *,
        documents: DocumentRepository,
        summaries: DocumentSummaryRepository,
        vector_store: VectorStoreGateway,
        file_storage: DocumentFileStorage,
        access_control: AccessControl,
    ) -> None:
        self._documents = documents
        self._summaries = summaries
        self._vector_store = vector_store
        self._storage = file_storage
        self._access = access_control

    def remove_for_conversation(
        self, conversation_id: ConversationId, *, actor: AuthenticatedUser
    ) -> None:
        """RF-120: a exclusao da conversa apaga o documento dela antes."""
        document = self._documents.get_personal_by_conversation(conversation_id)
        if document is not None:
            self.remove(document, reason="conversation_deleted", actor=actor)

    def remove(
        self, document: Document, *, reason: RemovalReason, actor: AuthenticatedUser
    ) -> Document:
        """Vetores -> original -> mini-resumos e resumo -> lapide -> auditoria.

        A mensagem com o resumo ja postada na conversa nao e apagada (D10).
        """
        if not document.is_personal:
            raise ValueError("only personal documents are removed here.")
        if document.status is DocumentStatus.EXPIRED:
            return document
        # Falha no Qdrant interrompe: o documento continua vencido e volta na
        # proxima rodada (T9).
        self._vector_store.delete_by_document(SUMMARIZER_COLLECTION, document.id)
        if document.storage_key:
            try:
                self._storage.delete(document.storage_key)
            except Exception:  # noqa: BLE001 - arquivo orfao nao vaza para a busca
                logger.exception(
                    "summary_document.original.delete_failed",
                    extra={"document_id": document.id.value},
                )
        if self._summaries.get(document.id) is not None:
            self._summaries.delete_content(document.id)
        expired = self._documents.save(document.mark_expired())
        self._access.audit(
            actor,
            AuditAction.SUMMARY_DOCUMENT_DELETED,
            resource_type=AuditResource.DOCUMENT,
            resource_id=document.id.value,
            details={
                "reason": reason,
                "owner_user_id": document.owner_user_id,
                "source_name": document.source_name,
                "conversation_id": (
                    document.conversation_id.value if document.conversation_id else None
                ),
            },
        )
        logger.info(
            "summary_document.removed",
            extra={"document_id": document.id.value, "reason": reason},
        )
        return expired
