"""Dubles de identidade, permissoes e auditoria (SPEC-004)."""

from __future__ import annotations

from src.application.services import AccessControl, AuditTrail
from src.domain import (
    AssistantId,
    AuditEvent,
    AuditQuery,
    AuthenticatedUser,
    DocumentId,
    Role,
)


def make_user(
    user_id: str = "user-1",
    *,
    roles: tuple[str, ...] = (Role.USER,),
    groups: tuple[str, ...] = (),
    name: str = "",
) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user_id,
        name=name or user_id,
        roles=frozenset(Role(role) for role in roles),
        groups=frozenset(groups),
    )


def admin(user_id: str = "admin-1") -> AuthenticatedUser:
    return make_user(user_id, roles=(Role.ADMIN,))


def curator(user_id: str = "curator-1", *groups: str) -> AuthenticatedUser:
    return make_user(user_id, roles=(Role.CURATOR,), groups=groups)


class InMemoryPermissionRepository:
    def __init__(self) -> None:
        self.assistant_groups: dict[str, frozenset[str]] = {}
        self.document_groups: dict[str, frozenset[str]] = {}
        self.document_assistant: dict[str, str] = {}
        self.fail_next_document_write = False

    def get_assistant_groups(self, assistant_id: AssistantId) -> frozenset[str]:
        return self.assistant_groups.get(assistant_id.value, frozenset())

    def list_assistant_groups(self) -> dict[str, frozenset[str]]:
        return {key: value for key, value in self.assistant_groups.items() if value}

    def set_assistant_groups(
        self,
        assistant_id: AssistantId,
        groups: frozenset[str],
    ) -> None:
        self.assistant_groups[assistant_id.value] = frozenset(groups)

    def get_document_groups(self, document_id: DocumentId) -> frozenset[str]:
        return self.document_groups.get(document_id.value, frozenset())

    def list_document_groups(
        self,
        assistant_id: AssistantId,
    ) -> dict[str, frozenset[str]]:
        return {
            key: value
            for key, value in self.document_groups.items()
            if value
            and self.document_assistant.get(key, assistant_id.value)
            == assistant_id.value
        }

    def set_document_groups(
        self,
        document_id: DocumentId,
        groups: frozenset[str],
    ) -> None:
        self.document_groups[document_id.value] = frozenset(groups)


class InMemoryAuditLog:
    """Como a porta: so inclui e consulta."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event

    def list_events(self, query: AuditQuery) -> list[AuditEvent]:
        matching = [
            event
            for event in reversed(self.events)
            if (query.user_id is None or event.user_id == query.user_id)
            and (query.action is None or event.action == query.action)
            and (
                query.assistant_id is None
                or event.details.get("assistant_id") == query.assistant_id
            )
            and (
                query.occurred_from is None
                or event.occurred_at >= query.occurred_from
            )
            and (query.occurred_to is None or event.occurred_at <= query.occurred_to)
        ]
        return matching[query.offset : query.offset + query.limit]

    def actions(self) -> list[str]:
        return [event.action for event in self.events]

    def last(self, action: str) -> AuditEvent:
        return next(
            event for event in reversed(self.events) if event.action == action
        )


class AccessFixture:
    """Controle de acesso com repositorios em memoria."""

    def __init__(self) -> None:
        self.permissions = InMemoryPermissionRepository()
        self.audit = InMemoryAuditLog()
        self.control = AccessControl(
            permission_repository=self.permissions,
            audit_trail=AuditTrail(self.audit),
        )

    def link_assistant(self, assistant_id: str, *groups: str) -> None:
        self.permissions.set_assistant_groups(
            AssistantId(assistant_id), frozenset(groups)
        )

    def restrict_document(self, document_id: str, *groups: str) -> None:
        self.permissions.set_document_groups(
            DocumentId(document_id), frozenset(groups)
        )
