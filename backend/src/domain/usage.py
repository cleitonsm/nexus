"""Consumo do LLM e limite de uso (SPEC-006: RF-57, RF-59, RN-32).

Tokens e custo sao registrados por pergunta. O custo e uma estimativa, pela
tabela de precos configurada; nao e uma fatura.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from .errors import DomainValidationError

MINUTE = timedelta(minutes=1)
DAY = timedelta(days=1)
# Teto de sanidade dos limites configurados na tela (0 desliga a janela).
MAX_LIMIT_VALUE = 1_000_000
_COST_QUANTUM = Decimal("0.000001")


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Tokens de entrada e de saida de uma ou mais chamadas ao LLM."""

    input_tokens: int = 0
    output_tokens: int = 0

    def __post_init__(self) -> None:
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise DomainValidationError("token usage must not be negative.")

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class LLMCompletion:
    """Resposta completa do LLM com o consumo da chamada."""

    text: str
    usage: TokenUsage = field(default_factory=TokenUsage)


@dataclass(frozen=True, slots=True)
class LLMStreamChunk:
    """Parte de uma resposta em streaming.

    ``text`` traz o trecho novo; o consumo chega, quando o provedor o informa,
    em uma parte final sem texto.
    """

    text: str = ""
    usage: TokenUsage | None = None


@dataclass(frozen=True, slots=True)
class LLMPricing:
    """Precos por mil tokens; ``currency`` so rotula a estimativa."""

    input_per_1k: Decimal = Decimal("0")
    output_per_1k: Decimal = Decimal("0")
    currency: str = "USD"

    def __post_init__(self) -> None:
        if self.input_per_1k < 0 or self.output_per_1k < 0:
            raise DomainValidationError("LLM prices must not be negative.")
        if not self.currency.strip():
            raise DomainValidationError("pricing currency must not be empty.")

    def estimate(self, usage: TokenUsage) -> Decimal:
        cost = (
            Decimal(usage.input_tokens) * self.input_per_1k
            + Decimal(usage.output_tokens) * self.output_per_1k
        ) / Decimal(1000)
        return cost.quantize(_COST_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class UsageRecord:
    """Uma pergunta feita ao chat: base do consumo e do limite de uso.

    Nao guarda texto algum (RNF-25). Sobrevive a exclusao da conversa, para
    que apagar conversas nao zere o limite diario.
    """

    id: str
    user_id: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    estimated_cost: Decimal = Decimal("0")
    conversation_id: str | None = None
    assistant_id: str | None = None
    # Nome de exibicao do token, para a tela de consumo; nao e texto do chat.
    user_name: str | None = None
    fallback_used: bool = False
    failed: bool = False
    occurred_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        for name in ("id", "user_id", "model"):
            if not str(getattr(self, name)).strip():
                raise DomainValidationError(f"usage record {name} must not be empty.")
        if self.estimated_cost < 0:
            raise DomainValidationError("estimated cost must not be negative.")


@dataclass(frozen=True, slots=True)
class UsageSummary:
    """Totais de um usuario ou de uma conversa no periodo consultado."""

    key: str
    questions: int
    input_tokens: int
    output_tokens: int
    estimated_cost: Decimal
    user_id: str | None = None
    assistant_id: str | None = None
    last_used_at: datetime | None = None
    user_name: str | None = None


@dataclass(frozen=True, slots=True)
class UsageQuery:
    occurred_from: datetime
    occurred_to: datetime
    limit: int = 100

    def __post_init__(self) -> None:
        if self.occurred_from > self.occurred_to:
            raise DomainValidationError("usage period must start before it ends.")
        if self.limit < 1:
            raise DomainValidationError("usage query limit must be positive.")


class UsageWindow(StrEnum):
    MINUTE = "minute"
    DAY = "day"


@dataclass(frozen=True, slots=True)
class UsageLimits:
    """Perguntas por usuario por minuto e por dia (SPEC-006 D3); 0 desliga."""

    per_minute: int = 20
    per_day: int = 500

    def __post_init__(self) -> None:
        for name in ("per_minute", "per_day"):
            value = getattr(self, name)
            if value < 0 or value > MAX_LIMIT_VALUE:
                raise DomainValidationError(
                    f"usage limit {name} must be between 0 and {MAX_LIMIT_VALUE}."
                )

    @property
    def enabled(self) -> bool:
        return self.per_minute > 0 or self.per_day > 0


@dataclass(frozen=True, slots=True)
class UsageLimitDecision:
    allowed: bool
    window: UsageWindow | None = None
    limit: int = 0
    retry_at: datetime | None = None


def evaluate_usage_limits(
    limits: UsageLimits,
    recent_questions: list[datetime],
    now: datetime,
) -> UsageLimitDecision:
    """RN-32: janelas deslizantes de 60 s e de 24 h.

    ``recent_questions`` sao os horarios das perguntas do usuario nas ultimas
    24 h. Bloqueada, a pergunta so volta a ser aceita quando perguntas
    antigas saem da janela; ``retry_at`` e esse instante. Se as duas janelas
    estiverem cheias, vale o instante mais distante.
    """
    blocked: list[UsageLimitDecision] = []
    for window, span, limit in (
        (UsageWindow.MINUTE, MINUTE, limits.per_minute),
        (UsageWindow.DAY, DAY, limits.per_day),
    ):
        decision = _evaluate_window(window, span, limit, recent_questions, now)
        if decision is not None:
            blocked.append(decision)
    if not blocked:
        return UsageLimitDecision(allowed=True)
    return max(blocked, key=lambda item: item.retry_at or now)


def _evaluate_window(
    window: UsageWindow,
    span: timedelta,
    limit: int,
    recent_questions: list[datetime],
    now: datetime,
) -> UsageLimitDecision | None:
    if limit <= 0:
        return None
    in_window = sorted(moment for moment in recent_questions if moment > now - span)
    if len(in_window) < limit:
        return None
    # Depois que esta pergunta sair da janela, restam limit - 1 perguntas.
    release = in_window[len(in_window) - limit]
    return UsageLimitDecision(
        allowed=False,
        window=window,
        limit=limit,
        retry_at=release + span,
    )
