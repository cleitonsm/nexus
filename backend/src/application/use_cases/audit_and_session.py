"""Sessao do usuario e consulta da trilha de auditoria (RF-45, UC-13)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.application.dto import AuditEventDTO, CurrentUserDTO
from src.application.services import AccessControl, AuditTrail
from src.domain import (
    AuditAction,
    AuditLogRepository,
    AuditQuery,
    AuditResource,
    AuditRetentionRepository,
    AuthenticatedUser,
    DomainValidationError,
)

MAX_AUDIT_PAGE_SIZE = 200

# Identidade do comando de manutencao: e com ela que a limpeza aparece na trilha.
MAINTENANCE_USER = AuthenticatedUser(
    id="system:maintenance",
    name="Manutencao (linha de comando)",
)


class DescribeCurrentUserUseCase:
    """Identidade lida do token.

    O frontend chama esta operacao uma vez ao abrir a sessao; cada chamada
    fica registrada como inicio de sessao (o login em si ocorre no Keycloak).
    """

    def __init__(self, access_control: AccessControl) -> None:
        self._access = access_control

    def execute(self, user: AuthenticatedUser) -> CurrentUserDTO:
        self._access.audit(
            user,
            AuditAction.SESSION_STARTED,
            resource_type=AuditResource.SESSION,
            details={
                "roles": sorted(role.value for role in user.roles),
                "groups": sorted(user.groups),
            },
        )
        return CurrentUserDTO.from_user(user)


@dataclass(frozen=True, slots=True)
class ListAuditEventsInput:
    user: AuthenticatedUser
    user_id: str | None = None
    action: str | None = None
    assistant_id: str | None = None
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None
    limit: int = 50
    offset: int = 0


class ListAuditEventsUseCase:
    """UC-13: so o administrador consulta; a propria consulta e registrada."""

    def __init__(
        self,
        *,
        audit_log_repository: AuditLogRepository,
        access_control: AccessControl,
    ) -> None:
        self._audit_log_repository = audit_log_repository
        self._access = access_control

    def execute(self, data: ListAuditEventsInput) -> list[AuditEventDTO]:
        self._access.require_audit_access(data.user)
        query = AuditQuery(
            user_id=_clean(data.user_id),
            action=_clean(data.action),
            assistant_id=_clean(data.assistant_id),
            occurred_from=data.occurred_from,
            occurred_to=data.occurred_to,
            limit=min(data.limit, MAX_AUDIT_PAGE_SIZE),
            offset=data.offset,
        )
        events = self._audit_log_repository.list_events(query)
        self._access.audit(
            data.user,
            AuditAction.AUDIT_CONSULTED,
            resource_type=AuditResource.AUDIT,
            details=_filters(query),
        )
        return [AuditEventDTO.from_entity(event) for event in events]


def _clean(value: str | None) -> str | None:
    return (value or "").strip() or None


def _filters(query: AuditQuery) -> dict[str, object]:
    filters: dict[str, object] = {
        "filter_user_id": query.user_id,
        "filter_action": query.action,
        "filter_assistant_id": query.assistant_id,
        "from": query.occurred_from.isoformat() if query.occurred_from else None,
        "to": query.occurred_to.isoformat() if query.occurred_to else None,
    }
    return {key: value for key, value in filters.items() if value is not None}


@dataclass(frozen=True, slots=True)
class PurgeAuditEventsInput:
    retention_days: int


@dataclass(frozen=True, slots=True)
class PurgeAuditEventsResult:
    removed: int
    cutoff: datetime


class PurgeAuditEventsUseCase:
    """D6: retencao da trilha (RNF-24) feita pelo operador, nunca pela API.

    Apaga os eventos mais antigos que a retencao e registra a propria
    limpeza, que fica na trilha como evento novo.
    """

    def __init__(
        self,
        *,
        retention_repository: AuditRetentionRepository,
        audit_trail: AuditTrail,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._retention_repository = retention_repository
        self._audit_trail = audit_trail
        self._clock = clock

    def execute(self, data: PurgeAuditEventsInput) -> PurgeAuditEventsResult:
        if data.retention_days < 1:
            raise DomainValidationError("audit retention must be at least one day.")
        cutoff = self._clock() - timedelta(days=data.retention_days)
        removed = self._retention_repository.purge_older_than(cutoff)
        self._audit_trail.record(
            MAINTENANCE_USER,
            AuditAction.AUDIT_PURGED,
            resource_type=AuditResource.AUDIT,
            details={
                "retention_days": data.retention_days,
                "cutoff": cutoff.isoformat(),
                "removed": removed,
            },
        )
        return PurgeAuditEventsResult(removed=removed, cutoff=cutoff)
