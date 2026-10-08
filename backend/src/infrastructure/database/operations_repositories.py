"""Repositorios da Fase 6: consumo, limite de uso, configuracoes e avaliacoes."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.domain import (
    DAY,
    FeedbackQuery,
    FeedbackRating,
    FeedbackReview,
    FeedbackStatus,
    MessageFeedback,
    UsageLimitDecision,
    UsageLimits,
    UsageQuery,
    UsageRecord,
    UsageSummary,
    evaluate_usage_limits,
)

from src.infrastructure.observability.metrics import GaugeSample

from .models import (
    AppSettingModel,
    IngestionJobModel,
    MessageFeedbackModel,
    UsageRecordModel,
)

USAGE_LIMITS_KEY = "usage_limits"


class PostgresUsageRecordRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, record: UsageRecord) -> UsageRecord:
        self._session.add(
            UsageRecordModel(
                id=record.id,
                user_id=record.user_id,
                user_name=record.user_name,
                conversation_id=record.conversation_id,
                assistant_id=record.assistant_id,
                model=record.model,
                input_tokens=record.usage.input_tokens,
                output_tokens=record.usage.output_tokens,
                estimated_cost=record.estimated_cost,
                fallback_used=record.fallback_used,
                failed=record.failed,
                occurred_at=record.occurred_at,
            )
        )
        self._session.commit()
        return record

    def summarize_by_user(self, query: UsageQuery) -> list[UsageSummary]:
        stmt = (
            self._totals(
                UsageRecordModel.user_id,
                func.max(UsageRecordModel.user_name).label("user_name"),
            )
            .where(*_period(query))
            .group_by(UsageRecordModel.user_id)
            .order_by(func.sum(UsageRecordModel.estimated_cost).desc())
            .limit(query.limit)
        )
        return [
            _summary(row, key=row.key, user_id=row.key, user_name=row.user_name)
            for row in self._session.execute(stmt).all()
        ]

    def summarize_by_conversation(self, query: UsageQuery) -> list[UsageSummary]:
        stmt = (
            self._totals(
                UsageRecordModel.conversation_id,
                UsageRecordModel.user_id,
                UsageRecordModel.assistant_id,
            )
            .add_columns(func.max(UsageRecordModel.user_name).label("user_name"))
            .where(*_period(query), UsageRecordModel.conversation_id.is_not(None))
            .group_by(
                UsageRecordModel.conversation_id,
                UsageRecordModel.user_id,
                UsageRecordModel.assistant_id,
            )
            .order_by(func.sum(UsageRecordModel.estimated_cost).desc())
            .limit(query.limit)
        )
        return [
            _summary(
                row,
                key=row.key,
                user_id=row.user_id,
                assistant_id=row.assistant_id,
                user_name=row.user_name,
            )
            for row in self._session.execute(stmt).all()
        ]

    @staticmethod
    def _totals(key_column, *extra):
        return select(
            key_column.label("key"),
            *extra,
            func.count(UsageRecordModel.id).label("questions"),
            func.coalesce(func.sum(UsageRecordModel.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(UsageRecordModel.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(UsageRecordModel.estimated_cost), 0).label("cost"),
            func.max(UsageRecordModel.occurred_at).label("last_used_at"),
        )


def _period(query: UsageQuery) -> tuple[object, ...]:
    return (
        UsageRecordModel.occurred_at >= query.occurred_from,
        UsageRecordModel.occurred_at <= query.occurred_to,
    )


def _summary(
    row,
    *,
    key: str,
    user_id: str | None = None,
    assistant_id: str | None = None,
    user_name: str | None = None,
) -> UsageSummary:
    return UsageSummary(
        key=key,
        questions=int(row.questions),
        input_tokens=int(row.input_tokens),
        output_tokens=int(row.output_tokens),
        estimated_cost=Decimal(row.cost),
        user_id=user_id,
        assistant_id=assistant_id,
        last_used_at=row.last_used_at,
        user_name=user_name,
    )


class PostgresUsageLimiter:
    """RN-32 sobre ``usage_records``: le as perguntas recentes do usuario.

    Basta ler as N mais recentes, com N o maior limite: a decisao so depende
    da pergunta que precisa sair da janela para liberar a proxima. Duas
    perguntas simultaneas podem passar juntas no limite (sem bloqueio de linha).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def check(
        self,
        user_id: str,
        limits: UsageLimits,
        now: datetime,
    ) -> UsageLimitDecision:
        most_recent = max(limits.per_minute, limits.per_day)
        if most_recent <= 0:
            return UsageLimitDecision(allowed=True)
        stmt = (
            select(UsageRecordModel.occurred_at)
            .where(
                UsageRecordModel.user_id == user_id,
                UsageRecordModel.occurred_at > now - DAY,
            )
            .order_by(UsageRecordModel.occurred_at.desc())
            .limit(most_recent)
        )
        moments = [_aware(item) for item in self._session.scalars(stmt).all()]
        return evaluate_usage_limits(limits, moments, now)


class PostgresUsageSettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_limits(self) -> UsageLimits | None:
        model = self._session.get(AppSettingModel, USAGE_LIMITS_KEY)
        if model is None:
            return None
        value = model.value or {}
        return UsageLimits(
            per_minute=int(value.get("per_minute", 0)),
            per_day=int(value.get("per_day", 0)),
        )

    def save_limits(self, limits: UsageLimits, *, updated_by: str) -> UsageLimits:
        value = {"per_minute": limits.per_minute, "per_day": limits.per_day}
        model = self._session.get(AppSettingModel, USAGE_LIMITS_KEY)
        now = datetime.now(UTC)
        if model is None:
            self._session.add(
                AppSettingModel(
                    key_name=USAGE_LIMITS_KEY,
                    value=value,
                    updated_by=updated_by,
                    updated_at=now,
                )
            )
        else:
            model.value = value
            model.updated_by = updated_by
            model.updated_at = now
        self._session.commit()
        return limits


class PostgresFeedbackRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, feedback: MessageFeedback) -> MessageFeedback:
        model = self._session.get(MessageFeedbackModel, feedback.id)
        if model is None:
            model = MessageFeedbackModel(id=feedback.id)
            self._session.add(model)
        _apply_feedback(model, feedback)
        self._session.commit()
        return feedback

    def get_by_id(self, feedback_id: str) -> MessageFeedback | None:
        model = self._session.get(MessageFeedbackModel, feedback_id)
        return _feedback_to_entity(model) if model is not None else None

    def get_by_message(self, message_id: str, user_id: str) -> MessageFeedback | None:
        stmt = select(MessageFeedbackModel).where(
            MessageFeedbackModel.message_id == message_id,
            MessageFeedbackModel.user_id == user_id,
        )
        model = self._session.scalars(stmt).first()
        return _feedback_to_entity(model) if model is not None else None

    def list_feedback(self, query: FeedbackQuery) -> list[MessageFeedback]:
        if query.assistant_ids is not None and not query.assistant_ids:
            return []
        stmt = select(MessageFeedbackModel)
        if query.assistant_ids is not None:
            stmt = stmt.where(MessageFeedbackModel.assistant_id.in_(sorted(query.assistant_ids)))
        if query.rating is not None:
            stmt = stmt.where(MessageFeedbackModel.rating == query.rating.value)
        if query.status is not None:
            stmt = stmt.where(MessageFeedbackModel.status == query.status.value)
        stmt = (
            stmt.order_by(MessageFeedbackModel.updated_at.desc(), MessageFeedbackModel.id)
            .limit(query.limit)
            .offset(query.offset)
        )
        return [_feedback_to_entity(item) for item in self._session.scalars(stmt).all()]


def _apply_feedback(model: MessageFeedbackModel, feedback: MessageFeedback) -> None:
    review = feedback.review
    model.message_id = feedback.message_id
    model.conversation_id = feedback.conversation_id
    model.assistant_id = feedback.assistant_id
    model.user_id = feedback.user_id
    model.rating = feedback.rating.value
    model.comment = feedback.comment
    model.question = feedback.question
    model.answer = feedback.answer
    model.cited_documents = list(feedback.cited_documents)
    model.status = feedback.status.value
    model.expected_answer = review.expected_answer if review else None
    model.source_documents = list(review.source_documents) if review else None
    model.out_of_scope = review.out_of_scope if review else False
    model.reviewed_by = feedback.reviewed_by
    model.reviewed_at = feedback.reviewed_at
    model.created_at = feedback.created_at
    model.updated_at = feedback.updated_at


def _feedback_to_entity(model: MessageFeedbackModel) -> MessageFeedback:
    status = FeedbackStatus(model.status)
    review = None
    if status is FeedbackStatus.VALIDATED:
        review = FeedbackReview(
            expected_answer=model.expected_answer,
            source_documents=tuple(model.source_documents or ()),
            out_of_scope=bool(model.out_of_scope),
        )
    return MessageFeedback(
        id=model.id,
        message_id=model.message_id,
        conversation_id=model.conversation_id,
        assistant_id=model.assistant_id,
        user_id=model.user_id,
        rating=FeedbackRating(model.rating),
        comment=model.comment,
        question=model.question,
        answer=model.answer,
        cited_documents=tuple(model.cited_documents or ()),
        status=status,
        review=review,
        reviewed_by=model.reviewed_by,
        reviewed_at=_aware(model.reviewed_at) if model.reviewed_at else None,
        created_at=_aware(model.created_at),
        updated_at=_aware(model.updated_at),
    )


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def ingestion_job_gauges(session_factory) -> list[GaugeSample]:
    """Jobs de ingestao por estado, para o ``/metrics`` (RF-57)."""
    with session_factory() as session:
        rows = session.execute(
            select(IngestionJobModel.status, func.count(IngestionJobModel.id)).group_by(
                IngestionJobModel.status
            )
        ).all()
    return [
        GaugeSample(name="nexus_ingestion_jobs", labels={"status": status}, value=count)
        for status, count in rows
    ]
