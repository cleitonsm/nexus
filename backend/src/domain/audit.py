"""Trilha de auditoria (RF-45, RN-25): eventos somente de inclusao."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from .errors import DomainValidationError


class AuditAction(StrEnum):
    SESSION_STARTED = "auth.session_started"
    ACCESS_DENIED = "access.denied"
    CHAT_QUESTION = "chat.question"
    ASSISTANT_CREATED = "assistant.created"
    ASSISTANT_DELETED = "assistant.deleted"
    ASSISTANT_GROUPS_CHANGED = "assistant.groups_changed"
    ASSISTANT_REINDEX_STARTED = "assistant.reindex_started"
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_GROUPS_CHANGED = "document.groups_changed"
    LLM_API_KEY_CHANGED = "llm_api_key.changed"
    LLM_API_KEY_TESTED = "llm_api_key.tested"
    AUDIT_CONSULTED = "audit.consulted"
    AUDIT_PURGED = "audit.purged"


class AuditResource(StrEnum):
    SESSION = "session"
    ASSISTANT = "assistant"
    DOCUMENT = "document"
    CONVERSATION = "conversation"
    SETTINGS = "settings"
    AUDIT = "audit"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Quem fez o que, quando e sobre qual recurso.

    ``details`` guarda identificadores e nomes de arquivo; nunca o texto de
    documentos, de perguntas ou de respostas (RN-24, RNF-25).
    """

    id: str
    user_id: str
    action: str
    resource_type: str
    resource_id: str | None = None
    details: dict[str, object] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        for name in ("id", "user_id", "action", "resource_type"):
            if not str(getattr(self, name)).strip():
                raise DomainValidationError(f"audit event {name} must not be empty.")


@dataclass(frozen=True, slots=True)
class AuditQuery:
    """Filtros da consulta (UC-13): periodo, usuario, assistente e tipo de evento."""

    user_id: str | None = None
    action: str | None = None
    assistant_id: str | None = None
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None
    limit: int = 50
    offset: int = 0

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise DomainValidationError("audit query limit must be positive.")
        if self.offset < 0:
            raise DomainValidationError("audit query offset must not be negative.")
        if (
            self.occurred_from is not None
            and self.occurred_to is not None
            and self.occurred_from > self.occurred_to
        ):
            raise DomainValidationError(
                "audit query period must start before it ends."
            )
