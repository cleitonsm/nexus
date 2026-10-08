"""Esquemas da Fase 6: avaliacoes, consumo e limites de uso (SPEC-006)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from src.domain.feedback import MAX_COMMENT_LENGTH, MAX_EXPECTED_ANSWER_LENGTH
from src.domain.usage import MAX_LIMIT_VALUE


class FeedbackRatingRequest(StrEnum):
    USEFUL = "util"
    NOT_USEFUL = "nao_util"


class SubmitFeedbackRequest(BaseModel):
    rating: FeedbackRatingRequest
    comment: str | None = Field(default=None, max_length=MAX_COMMENT_LENGTH)


class ReviewDecision(StrEnum):
    VALIDATED = "validado"
    DISCARDED = "descartado"


class ReviewFeedbackRequest(BaseModel):
    decision: ReviewDecision
    expected_answer: str | None = Field(
        default=None, max_length=MAX_EXPECTED_ANSWER_LENGTH
    )
    source_documents: list[str] = Field(default_factory=list, max_length=20)
    out_of_scope: bool = False


class FeedbackResponse(BaseModel):
    id: str
    message_id: str
    conversation_id: str
    assistant_id: str
    rating: str
    comment: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    question: str | None = None
    answer: str | None = None
    cited_documents: list[str] = Field(default_factory=list)
    expected_answer: str | None = None
    source_documents: list[str] = Field(default_factory=list)
    out_of_scope: bool = False
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


class UsageSummaryResponse(BaseModel):
    key: str
    questions: int
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    user_id: str | None = None
    assistant_id: str | None = None
    last_used_at: datetime | None = None
    user_name: str | None = None


class UsageReportResponse(BaseModel):
    occurred_from: datetime
    occurred_to: datetime
    currency: str
    model: str
    # O custo e uma estimativa pela tabela de precos configurada, nao uma fatura.
    estimated: bool = True
    by_user: list[UsageSummaryResponse]
    by_conversation: list[UsageSummaryResponse]
    total_questions: int
    total_input_tokens: int
    total_output_tokens: int
    total_estimated_cost: float


class UsageLimitsRequest(BaseModel):
    per_minute: int = Field(ge=0, le=MAX_LIMIT_VALUE)
    per_day: int = Field(ge=0, le=MAX_LIMIT_VALUE)


class UsageLimitsResponse(BaseModel):
    per_minute: int
    per_day: int
    source: str
