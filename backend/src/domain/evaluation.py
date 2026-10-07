from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .errors import DomainValidationError
from .value_objects import AssistantId


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class EvaluationItem:
    """Pergunta de referencia usada para medir o pipeline de RAG."""

    id: str
    question: str
    expected_answer: str | None = None
    source_documents: tuple[str, ...] = ()
    out_of_scope: bool = False
    validated_by: str | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise DomainValidationError("evaluation item id must not be empty.")
        if not self.question.strip():
            raise DomainValidationError(
                "evaluation item question must not be empty."
            )
        if self.out_of_scope:
            return
        if not (self.expected_answer or "").strip():
            raise DomainValidationError(
                "in-scope evaluation item requires expected_answer."
            )
        if not any(name.strip() for name in self.source_documents):
            raise DomainValidationError(
                "in-scope evaluation item requires source_documents."
            )

    @property
    def is_validated(self) -> bool:
        return bool((self.validated_by or "").strip())


@dataclass(frozen=True, slots=True)
class EvaluationItemResult:
    item_id: str
    out_of_scope: bool
    retrieved_sources: tuple[str, ...]
    first_relevant_rank: int | None
    fallback_used: bool | None
    faithful: bool | None


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    recall_at_k: float
    mrr: float
    faithfulness: float | None
    fallback_accuracy: float | None


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    assistant_id: AssistantId
    k: int
    metrics: EvaluationMetrics
    item_results: tuple[EvaluationItemResult, ...]
    validated: bool
    parameters: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)


def first_relevant_rank(
    retrieved_sources: Sequence[str],
    relevant_sources: Collection[str],
) -> int | None:
    """Posicao (a partir de 1) do primeiro resultado de um documento de origem."""
    for position, source in enumerate(retrieved_sources, start=1):
        if source in relevant_sources:
            return position
    return None


def recall_at_k(ranks: Sequence[int | None], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be positive.")
    if not ranks:
        return 0.0
    found = sum(1 for rank in ranks if rank is not None and rank <= k)
    return found / len(ranks)


def mean_reciprocal_rank(ranks: Sequence[int | None]) -> float:
    if not ranks:
        return 0.0
    total = sum(1 / rank for rank in ranks if rank is not None)
    return total / len(ranks)
