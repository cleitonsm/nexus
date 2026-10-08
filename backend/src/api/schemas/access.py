from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CurrentUserResponse(BaseModel):
    id: str
    name: str
    roles: list[str]
    groups: list[str]


class GroupsRequest(BaseModel):
    """Lista completa de grupos; substitui a anterior. Vazia remove todos."""

    groups: list[str] = Field(default_factory=list, max_length=100)


class GroupsResponse(BaseModel):
    groups: list[str]


class DocumentAccessResponse(BaseModel):
    """Documento, seu estado (RF-49) e sua restricao por grupo (RF-43)."""

    id: str
    assistant_id: str
    source_name: str
    created_at: datetime
    chunk_count: int
    groups: list[str]
    status: str
    version: int
    failure_reason: str | None = None
    size_bytes: int | None = None
    replaces_document_id: str | None = None
    content_hash: str
    has_original: bool


class AuditEventResponse(BaseModel):
    id: str
    occurred_at: datetime
    user_id: str
    action: str
    resource_type: str
    resource_id: str | None
    details: dict[str, object]
