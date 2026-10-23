"""Consumo e limites de uso, para o administrador (SPEC-006: RF-57, RF-59)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.application.dto import UsageLimitsDTO, UsageReportDTO, UsageSummaryDTO
from src.application.services import AccessControl, UsageSettings
from src.domain import (
    AuditAction,
    AuditResource,
    AuthenticatedUser,
    UsageLimits,
    UsageQuery,
    UsageRecordRepository,
    UsageSettingsRepository,
)

DEFAULT_REPORT_DAYS = 30
MAX_REPORT_ROWS = 500


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class GetUsageReportInput:
    user: AuthenticatedUser
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None
    limit: int = 100


class GetUsageReportUseCase:
    """Tokens e custo estimado por usuario e por conversa no periodo.

    Sem periodo, os ultimos 30 dias. O custo e estimado pela tabela de precos
    vigente no momento de cada pergunta.
    """

    def __init__(
        self,
        *,
        record_repository: UsageRecordRepository,
        access_control: AccessControl,
        settings: UsageSettings,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._records = record_repository
        self._access = access_control
        self._settings = settings
        self._clock = clock

    def execute(self, data: GetUsageReportInput) -> UsageReportDTO:
        self._access.require_admin(data.user, AuditAction.USAGE_CONSULTED)
        occurred_to = data.occurred_to or self._clock()
        occurred_from = data.occurred_from or occurred_to - timedelta(
            days=DEFAULT_REPORT_DAYS
        )
        query = UsageQuery(
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            limit=min(max(data.limit, 1), MAX_REPORT_ROWS),
        )
        by_user = self._records.summarize_by_user(query)
        by_conversation = self._records.summarize_by_conversation(query)
        self._access.audit(
            data.user,
            AuditAction.USAGE_CONSULTED,
            resource_type=AuditResource.SETTINGS,
            details={
                "from": occurred_from.isoformat(),
                "to": occurred_to.isoformat(),
            },
        )
        return UsageReportDTO(
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            currency=self._settings.pricing.currency,
            model=self._settings.model,
            by_user=tuple(UsageSummaryDTO.from_summary(item) for item in by_user),
            by_conversation=tuple(
                UsageSummaryDTO.from_summary(item) for item in by_conversation
            ),
            total_questions=sum(item.questions for item in by_user),
            total_input_tokens=sum(item.input_tokens for item in by_user),
            total_output_tokens=sum(item.output_tokens for item in by_user),
            total_estimated_cost=float(
                sum((item.estimated_cost for item in by_user), Decimal("0"))
            ),
        )


class GetUsageLimitsUseCase:
    def __init__(
        self,
        *,
        settings_repository: UsageSettingsRepository,
        access_control: AccessControl,
        settings: UsageSettings,
    ) -> None:
        self._repository = settings_repository
        self._access = access_control
        self._settings = settings

    def execute(self, user: AuthenticatedUser) -> UsageLimitsDTO:
        self._access.require_admin(user, AuditAction.USAGE_LIMITS_CHANGED)
        stored = self._repository.get_limits()
        return UsageLimitsDTO.from_limits(
            stored or self._settings.default_limits,
            stored=stored is not None,
        )


@dataclass(frozen=True, slots=True)
class UpdateUsageLimitsInput:
    user: AuthenticatedUser
    per_minute: int
    per_day: int


class UpdateUsageLimitsUseCase:
    """D3: os limites sao ajustados na tela e valem a partir da proxima pergunta."""

    def __init__(
        self,
        *,
        settings_repository: UsageSettingsRepository,
        access_control: AccessControl,
    ) -> None:
        self._repository = settings_repository
        self._access = access_control

    def execute(self, data: UpdateUsageLimitsInput) -> UsageLimitsDTO:
        self._access.require_admin(data.user, AuditAction.USAGE_LIMITS_CHANGED)
        limits = UsageLimits(per_minute=data.per_minute, per_day=data.per_day)
        previous = self._repository.get_limits()
        saved = self._repository.save_limits(limits, updated_by=data.user.id)
        self._access.audit(
            data.user,
            AuditAction.USAGE_LIMITS_CHANGED,
            resource_type=AuditResource.SETTINGS,
            details={
                "per_minute": saved.per_minute,
                "per_day": saved.per_day,
                "previous_per_minute": previous.per_minute if previous else None,
                "previous_per_day": previous.per_day if previous else None,
            },
        )
        return UsageLimitsDTO.from_limits(saved, stored=True)
