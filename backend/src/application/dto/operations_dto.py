"""DTOs da Fase 6: avaliacoes, consumo e limites de uso (SPEC-006)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain import MessageFeedback, UsageLimits, UsageSummary


@dataclass(frozen=True, slots=True)
class FeedbackDTO:
    id: str
    message_id: str
    conversation_id: str
    assistant_id: str
    rating: str
    comment: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    # So na visao do curador; o usuario nao precisa recebe-los de volta.
    question: str | None = None
    answer: str | None = None
    cited_documents: tuple[str, ...] = ()
    expected_answer: str | None = None
    source_documents: tuple[str, ...] = ()
    out_of_scope: bool = False
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None

    @classmethod
    def for_author(cls, feedback: MessageFeedback) -> "FeedbackDTO":
        return cls(
            id=feedback.id,
            message_id=feedback.message_id,
            conversation_id=feedback.conversation_id,
            assistant_id=feedback.assistant_id,
            rating=feedback.rating.value,
            comment=feedback.comment,
            status=feedback.status.value,
            created_at=feedback.created_at,
            updated_at=feedback.updated_at,
        )

    @classmethod
    def for_curator(cls, feedback: MessageFeedback) -> "FeedbackDTO":
        review = feedback.review
        return cls(
            id=feedback.id,
            message_id=feedback.message_id,
            conversation_id=feedback.conversation_id,
            assistant_id=feedback.assistant_id,
            rating=feedback.rating.value,
            comment=feedback.comment,
            status=feedback.status.value,
            created_at=feedback.created_at,
            updated_at=feedback.updated_at,
            question=feedback.question,
            answer=feedback.answer,
            cited_documents=feedback.cited_documents,
            expected_answer=review.expected_answer if review else None,
            source_documents=review.source_documents if review else (),
            out_of_scope=review.out_of_scope if review else False,
            reviewed_by=feedback.reviewed_by,
            reviewed_at=feedback.reviewed_at,
        )


@dataclass(frozen=True, slots=True)
class UsageSummaryDTO:
    key: str
    questions: int
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    user_id: str | None = None
    assistant_id: str | None = None
    last_used_at: datetime | None = None
    user_name: str | None = None

    @classmethod
    def from_summary(cls, summary: UsageSummary) -> "UsageSummaryDTO":
        return cls(
            key=summary.key,
            questions=summary.questions,
            input_tokens=summary.input_tokens,
            output_tokens=summary.output_tokens,
            estimated_cost=float(summary.estimated_cost),
            user_id=summary.user_id,
            assistant_id=summary.assistant_id,
            last_used_at=summary.last_used_at,
            user_name=summary.user_name,
        )


@dataclass(frozen=True, slots=True)
class UsageReportDTO:
    occurred_from: datetime
    occurred_to: datetime
    currency: str
    model: str
    by_user: tuple[UsageSummaryDTO, ...]
    by_conversation: tuple[UsageSummaryDTO, ...]
    total_questions: int
    total_input_tokens: int
    total_output_tokens: int
    total_estimated_cost: float


@dataclass(frozen=True, slots=True)
class UsageLimitsDTO:
    per_minute: int
    per_day: int
    # "configurado" quando gravado pela tela; "padrao" quando vem do ambiente.
    source: str

    @classmethod
    def from_limits(cls, limits: UsageLimits, *, stored: bool) -> "UsageLimitsDTO":
        return cls(
            per_minute=limits.per_minute,
            per_day=limits.per_day,
            source="configurado" if stored else "padrao",
        )
