from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from src.domain import (
    AccessDeniedError,
    AccessPolicy,
    Assistant,
    AssistantId,
    AssistantPermissionRepository,
    AuditAction,
    AuditEvent,
    AuditLogRepository,
    AuditResource,
    AuthenticatedUser,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AuditTrail:
    """Grava eventos na trilha; nao oferece alteracao nem exclusao (RN-25)."""

    def __init__(
        self,
        repository: AuditLogRepository,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def record(
        self,
        user: AuthenticatedUser,
        action: AuditAction,
        *,
        resource_type: AuditResource,
        resource_id: str | None = None,
        details: dict[str, object] | None = None,
    ) -> AuditEvent:
        return self._repository.append(
            AuditEvent(
                id=str(uuid4()),
                user_id=user.id,
                action=action.value,
                resource_type=resource_type.value,
                resource_id=resource_id,
                details={"user_name": user.name, **(details or {})},
                occurred_at=self._clock(),
            )
        )


class AccessControl:
    """Ponto unico em que os casos de uso consultam a ``AccessPolicy``.

    Toda negacao levanta ``AccessDeniedError`` e fica registrada na auditoria
    (HU-24). Os casos de uso tambem gravam por aqui os eventos do RF-45.
    """

    def __init__(
        self,
        *,
        permission_repository: AssistantPermissionRepository,
        audit_trail: AuditTrail,
    ) -> None:
        self._permissions = permission_repository
        self._audit_trail = audit_trail

    @property
    def permissions(self) -> AssistantPermissionRepository:
        return self._permissions

    def audit(
        self,
        user: AuthenticatedUser,
        action: AuditAction,
        *,
        resource_type: AuditResource,
        resource_id: str | None = None,
        details: dict[str, object] | None = None,
    ) -> AuditEvent:
        return self._audit_trail.record(
            user,
            action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )

    def visible_assistants(
        self,
        user: AuthenticatedUser,
        assistants: list[Assistant],
    ) -> list[tuple[Assistant, frozenset[str]]]:
        """RF-42: cada assistente visivel ao usuario, com os grupos vinculados."""
        groups_by_assistant = self._permissions.list_assistant_groups()
        visible: list[tuple[Assistant, frozenset[str]]] = []
        for assistant in assistants:
            groups = groups_by_assistant.get(assistant.id.value, frozenset())
            if AccessPolicy.can_access_assistant(user, groups):
                visible.append((assistant, groups))
        return visible

    def can_manage_documents(
        self,
        user: AuthenticatedUser,
        assistant_groups: frozenset[str],
    ) -> bool:
        return AccessPolicy.can_manage_documents(user, assistant_groups)

    def owns_conversation(
        self,
        user: AuthenticatedUser,
        owner_user_id: str | None,
    ) -> bool:
        return AccessPolicy.owns_conversation(user, owner_user_id)

    def require_admin(self, user: AuthenticatedUser, attempted: AuditAction) -> None:
        if not AccessPolicy.can_manage_assistants(user):
            self._deny(user, attempted, AuditResource.SETTINGS, None)

    def require_llm_configuration(
        self,
        user: AuthenticatedUser,
        attempted: AuditAction,
    ) -> None:
        """RF-47: a chave do LLM e do administrador."""
        if not AccessPolicy.can_configure_llm(user):
            self._deny(user, attempted, AuditResource.SETTINGS, None)

    def manageable_assistant_ids(
        self,
        user: AuthenticatedUser,
    ) -> frozenset[str] | None:
        """Assistentes cuja base o usuario cura; ``None`` significa todos (admin)."""
        if user.is_admin:
            return None
        if not user.is_curator:
            return frozenset()
        return frozenset(
            assistant_id
            for assistant_id, groups in self._permissions.list_assistant_groups().items()
            if AccessPolicy.can_manage_documents(user, groups)
        )

    def require_curation(
        self,
        user: AuthenticatedUser,
        attempted: AuditAction,
    ) -> frozenset[str] | None:
        """RN-33: avaliacoes negativas sao do curador (ou do administrador)."""
        scope = self.manageable_assistant_ids(user)
        if scope is not None and not user.is_curator:
            self._deny(user, attempted, AuditResource.FEEDBACK, None)
        return scope

    def require_group_listing(self, user: AuthenticatedUser) -> None:
        """PC-D6: quem vincula grupos (administrador) ou restringe documentos
        (curador) consulta a lista de grupos do Keycloak."""
        if not (user.is_admin or user.is_curator):
            self._deny(user, "groups.listed", AuditResource.SETTINGS, None)

    def require_audit_access(self, user: AuthenticatedUser) -> None:
        if not AccessPolicy.can_view_audit(user):
            self._deny(user, AuditAction.AUDIT_CONSULTED, AuditResource.AUDIT, None)

    def require_assistant_access(
        self,
        user: AuthenticatedUser,
        assistant_id: AssistantId,
        attempted: AuditAction | str,
    ) -> frozenset[str]:
        """Devolve os grupos do assistente quando o usuario pode usa-lo."""
        groups = self._permissions.get_assistant_groups(assistant_id)
        if not AccessPolicy.can_access_assistant(user, groups):
            self._deny(user, attempted, AuditResource.ASSISTANT, assistant_id.value)
        return groups

    def require_document_management(
        self,
        user: AuthenticatedUser,
        assistant_id: AssistantId,
        attempted: AuditAction | str,
    ) -> frozenset[str]:
        groups = self._permissions.get_assistant_groups(assistant_id)
        if not AccessPolicy.can_manage_documents(user, groups):
            self._deny(user, attempted, AuditResource.ASSISTANT, assistant_id.value)
        return groups

    def _deny(
        self,
        user: AuthenticatedUser,
        attempted: AuditAction | str,
        resource_type: AuditResource,
        resource_id: str | None,
    ) -> None:
        details: dict[str, object] = {"attempted_action": str(attempted)}
        if resource_type is AuditResource.ASSISTANT and resource_id:
            details["assistant_id"] = resource_id
        self._audit_trail.record(
            user,
            AuditAction.ACCESS_DENIED,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )
        raise AccessDeniedError("you do not have permission for this operation.")
