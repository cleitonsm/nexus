from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.domain import AuditEvent, AuthenticatedUser, Document, DocumentStatus


@dataclass(frozen=True, slots=True)
class CurrentUserDTO:
    id: str
    name: str
    roles: tuple[str, ...]
    groups: tuple[str, ...]

    @classmethod
    def from_user(cls, user: AuthenticatedUser) -> "CurrentUserDTO":
        return cls(
            id=user.id,
            name=user.name,
            roles=tuple(sorted(role.value for role in user.roles)),
            groups=tuple(sorted(user.groups)),
        )


@dataclass(frozen=True, slots=True)
class DocumentAccessDTO:
    """Documento de um assistente, seu estado (RF-49) e sua restricao (RF-43)."""

    id: str
    assistant_id: str
    source_name: str
    created_at: datetime
    chunk_count: int
    groups: tuple[str, ...] = ()
    status: str = DocumentStatus.INDEXED.value
    version: int = 1
    failure_reason: str | None = None
    size_bytes: int | None = None
    replaces_document_id: str | None = None
    content_hash: str = ""
    has_original: bool = False

    @classmethod
    def from_entity(
        cls,
        document: Document,
        groups: frozenset[str] = frozenset(),
    ) -> "DocumentAccessDTO":
        return cls(
            id=document.id.value,
            assistant_id=document.assistant_id.value,
            source_name=document.source_name,
            created_at=document.created_at,
            chunk_count=document.chunk_count,
            groups=tuple(sorted(groups)),
            status=document.status.value,
            version=document.version,
            failure_reason=document.failure_reason,
            size_bytes=document.size_bytes,
            replaces_document_id=(
                document.replaces_document_id.value
                if document.replaces_document_id
                else None
            ),
            content_hash=document.content_hash,
            has_original=document.has_original,
        )


@dataclass(frozen=True, slots=True)
class AuditEventDTO:
    id: str
    occurred_at: datetime
    user_id: str
    action: str
    resource_type: str
    resource_id: str | None
    details: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_entity(cls, event: AuditEvent) -> "AuditEventDTO":
        return cls(
            id=event.id,
            occurred_at=event.occurred_at,
            user_id=event.user_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            details=dict(event.details),
        )
