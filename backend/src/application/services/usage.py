"""Limite de uso e registro de consumo das perguntas (SPEC-006: RF-57, RF-59)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from src.domain import (
    AuthenticatedUser,
    LLMPricing,
    MetricsRecorder,
    NoopMetrics,
    TokenUsage,
    UsageLimiter,
    UsageLimitExceededError,
    UsageLimits,
    UsageRecord,
    UsageRecordRepository,
    UsageSettingsRepository,
)

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class UsageSettings:
    """Padroes do ambiente; os limites gravados pela tela tem precedencia."""

    default_limits: UsageLimits = field(default_factory=UsageLimits)
    pricing: LLMPricing = field(default_factory=LLMPricing)
    model: str = "gpt-4o-mini"


class UsageGovernance:
    """Ponto unico do chat para o limite de uso e o registro de consumo."""

    def __init__(
        self,
        *,
        limiter: UsageLimiter,
        record_repository: UsageRecordRepository,
        settings_repository: UsageSettingsRepository,
        settings: UsageSettings,
        metrics: MetricsRecorder | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._limiter = limiter
        self._records = record_repository
        self._settings_repository = settings_repository
        self._settings = settings
        self._metrics = metrics or NoopMetrics()
        self._clock = clock

    @property
    def settings(self) -> UsageSettings:
        return self._settings

    def current_limits(self) -> UsageLimits:
        return self._settings_repository.get_limits() or self._settings.default_limits

    def check(self, user: AuthenticatedUser) -> None:
        """RN-32: levanta ``UsageLimitExceededError`` com a proxima janela."""
        limits = self.current_limits()
        if not limits.enabled:
            return
        decision = self._limiter.check(user.id, limits, self._clock())
        if decision.allowed:
            return
        window = decision.window.value if decision.window else "minute"
        self._metrics.increment(
            "nexus_usage_limit_blocked_total", labels={"window": window}
        )
        logger.info(
            "chat.usage_limit.blocked",
            extra={"window": window, "limit": decision.limit},
        )
        raise UsageLimitExceededError(
            "usage limit reached for this window.",
            window=window,
            limit=decision.limit,
            retry_at=decision.retry_at or self._clock(),
        )

    def record(
        self,
        user: AuthenticatedUser,
        *,
        conversation_id: str | None,
        assistant_id: str | None,
        usage: TokenUsage,
        fallback_used: bool = False,
        failed: bool = False,
    ) -> UsageRecord:
        model = self._settings.model
        record = self._records.append(
            UsageRecord(
                id=str(uuid4()),
                user_id=user.id,
                model=model,
                usage=usage,
                estimated_cost=self._settings.pricing.estimate(usage),
                conversation_id=conversation_id,
                assistant_id=assistant_id,
                user_name=user.name,
                fallback_used=fallback_used,
                failed=failed,
                occurred_at=self._clock(),
            )
        )
        labels = {"model": model}
        self._metrics.increment(
            "nexus_llm_tokens_total",
            usage.input_tokens,
            {**labels, "direction": "input"},
        )
        self._metrics.increment(
            "nexus_llm_tokens_total",
            usage.output_tokens,
            {**labels, "direction": "output"},
        )
        self._metrics.increment(
            "nexus_llm_estimated_cost_total",
            float(record.estimated_cost),
            {**labels, "currency": self._settings.pricing.currency},
        )
        return record
