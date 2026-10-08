"""Dubles da Fase 6: consumo, limite de uso, avaliacoes e rastreamento."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.domain import (
    DAY,
    FeedbackQuery,
    MessageFeedback,
    UsageLimitDecision,
    UsageLimits,
    UsageQuery,
    UsageRecord,
    UsageSummary,
    evaluate_usage_limits,
)

BASE_NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


class Clock:
    """Relogio deslocavel."""

    def __init__(self, now: datetime = BASE_NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now = self.now + timedelta(**delta)


class InMemoryUsageRecords:
    """Repositorio de consumo e limitador sobre a mesma lista, como no banco."""

    def __init__(self) -> None:
        self.records: list[UsageRecord] = []

    def append(self, record: UsageRecord) -> UsageRecord:
        self.records.append(record)
        return record

    def check(
        self,
        user_id: str,
        limits: UsageLimits,
        now: datetime,
    ) -> UsageLimitDecision:
        moments = [
            item.occurred_at
            for item in self.records
            if item.user_id == user_id and item.occurred_at > now - DAY
        ]
        return evaluate_usage_limits(limits, moments, now)

    def summarize_by_user(self, query: UsageQuery) -> list[UsageSummary]:
        return self._summarize(query, lambda item: item.user_id)

    def summarize_by_conversation(self, query: UsageQuery) -> list[UsageSummary]:
        return self._summarize(
            query,
            lambda item: item.conversation_id,
        )

    def _summarize(self, query: UsageQuery, key_of) -> list[UsageSummary]:
        groups: dict[str, list[UsageRecord]] = {}
        for item in self.records:
            key = key_of(item)
            if key is None:
                continue
            if query.occurred_from <= item.occurred_at <= query.occurred_to:
                groups.setdefault(key, []).append(item)
        summaries = [
            UsageSummary(
                key=key,
                questions=len(items),
                input_tokens=sum(i.usage.input_tokens for i in items),
                output_tokens=sum(i.usage.output_tokens for i in items),
                estimated_cost=sum((i.estimated_cost for i in items), Decimal("0")),
                user_id=items[0].user_id,
                assistant_id=items[0].assistant_id,
                last_used_at=max(i.occurred_at for i in items),
                user_name=items[0].user_name,
            )
            for key, items in groups.items()
        ]
        summaries.sort(key=lambda item: item.estimated_cost, reverse=True)
        return summaries[: query.limit]


class InMemoryUsageSettings:
    def __init__(self, limits: UsageLimits | None = None) -> None:
        self.limits = limits
        self.updated_by: str | None = None

    def get_limits(self) -> UsageLimits | None:
        return self.limits

    def save_limits(self, limits: UsageLimits, *, updated_by: str) -> UsageLimits:
        self.limits = limits
        self.updated_by = updated_by
        return limits


class InMemoryFeedback:
    def __init__(self) -> None:
        self.items: dict[str, MessageFeedback] = {}

    def save(self, feedback: MessageFeedback) -> MessageFeedback:
        self.items[feedback.id] = feedback
        return feedback

    def get_by_id(self, feedback_id: str) -> MessageFeedback | None:
        return self.items.get(feedback_id)

    def get_by_message(self, message_id: str, user_id: str) -> MessageFeedback | None:
        for item in self.items.values():
            if item.message_id == message_id and item.user_id == user_id:
                return item
        return None

    def list_feedback(self, query: FeedbackQuery) -> list[MessageFeedback]:
        if query.assistant_ids is not None and not query.assistant_ids:
            return []
        matching = [
            item
            for item in self.items.values()
            if (query.assistant_ids is None or item.assistant_id in query.assistant_ids)
            and (query.rating is None or item.rating is query.rating)
            and (query.status is None or item.status is query.status)
        ]
        matching.sort(key=lambda item: item.updated_at, reverse=True)
        return matching[query.offset : query.offset + query.limit]


@dataclass
class RecordedSpan:
    name: str
    attributes: dict[str, object] = field(default_factory=dict)
    parent: str | None = None
    error: str | None = None

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def record_error(self, error: BaseException) -> None:
        self.error = type(error).__name__


class RecordingTracer:
    """Registra os trechos abertos, com o nome do trecho pai."""

    def __init__(self) -> None:
        self.spans: list[RecordedSpan] = []
        self._stack: list[RecordedSpan] = []

    @contextmanager
    def span(
        self,
        name: str,
        attributes: Mapping[str, object] | None = None,
    ) -> Iterator[RecordedSpan]:
        record = RecordedSpan(
            name=name,
            attributes=dict(attributes or {}),
            parent=self._stack[-1].name if self._stack else None,
        )
        self.spans.append(record)
        self._stack.append(record)
        try:
            yield record
        except Exception as exc:
            record.record_error(exc)
            raise
        finally:
            self._stack.pop()

    def names(self) -> list[str]:
        return [span.name for span in self.spans]


class RecordingMetrics:
    def __init__(self) -> None:
        self.counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self.observations: list[tuple[str, float]] = []

    def increment(
        self,
        name: str,
        value: float = 1.0,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        key = (name, tuple(sorted((labels or {}).items())))
        self.counters[key] = self.counters.get(key, 0.0) + value

    def observe(
        self,
        name: str,
        value: float,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        self.observations.append((name, value))

    def total(self, name: str, **labels: str) -> float:
        wanted = set(labels.items())
        return sum(
            value
            for (metric, key), value in self.counters.items()
            if metric == name and wanted <= set(key)
        )
