"""Avaliacao das respostas pelo usuario (SPEC-006: RF-61, RN-33)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum

from .errors import DomainValidationError, InvalidFeedbackStateError
from .evaluation import EvaluationItem

MAX_COMMENT_LENGTH = 1000
MAX_EXPECTED_ANSWER_LENGTH = 4000


def _utc_now() -> datetime:
    return datetime.now(UTC)


class FeedbackRating(StrEnum):
    USEFUL = "util"
    NOT_USEFUL = "nao_util"


class FeedbackStatus(StrEnum):
    """So avaliacao negativa passa pelo curador (RN-33)."""

    NOT_APPLICABLE = "nao_aplicavel"
    PENDING = "pendente"
    VALIDATED = "validado"
    DISCARDED = "descartado"


@dataclass(frozen=True, slots=True)
class FeedbackReview:
    """O que o curador confirma ao validar: vira item de referencia."""

    expected_answer: str | None = None
    source_documents: tuple[str, ...] = ()
    out_of_scope: bool = False

    def __post_init__(self) -> None:
        answer = (self.expected_answer or "").strip()
        if len(answer) > MAX_EXPECTED_ANSWER_LENGTH:
            raise DomainValidationError(
                f"expected answer must be at most {MAX_EXPECTED_ANSWER_LENGTH} characters."
            )
        sources = tuple(name.strip() for name in self.source_documents if name.strip())
        object.__setattr__(self, "expected_answer", answer or None)
        object.__setattr__(self, "source_documents", sources)
        if self.out_of_scope:
            return
        if not answer or not sources:
            raise DomainValidationError(
                "an in-scope reference item requires expected_answer and source_documents."
            )


@dataclass(frozen=True, slots=True)
class MessageFeedback:
    """Avaliacao de uma resposta do assistente por quem fez a pergunta.

    Uma por usuario e mensagem; a mais recente substitui a anterior. Na
    avaliacao negativa a pergunta e a resposta sao copiadas para que o curador
    as analise sem acesso a conversa, que continua privada (RN-24); o usuario
    e avisado disso na tela antes de enviar.
    """

    id: str
    message_id: str
    conversation_id: str
    assistant_id: str
    user_id: str
    rating: FeedbackRating
    comment: str | None = None
    question: str | None = None
    answer: str | None = None
    cited_documents: tuple[str, ...] = ()
    status: FeedbackStatus = FeedbackStatus.NOT_APPLICABLE
    review: FeedbackReview | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        for name in ("id", "message_id", "conversation_id", "assistant_id", "user_id"):
            if not str(getattr(self, name)).strip():
                raise DomainValidationError(f"feedback {name} must not be empty.")
        object.__setattr__(self, "rating", FeedbackRating(self.rating))
        object.__setattr__(self, "status", FeedbackStatus(self.status))
        comment = (self.comment or "").strip()
        if len(comment) > MAX_COMMENT_LENGTH:
            raise DomainValidationError(
                f"feedback comment must be at most {MAX_COMMENT_LENGTH} characters."
            )
        object.__setattr__(self, "comment", comment or None)
        if self.rating is FeedbackRating.USEFUL:
            self._check_useful()
        elif self.status is FeedbackStatus.NOT_APPLICABLE:
            raise DomainValidationError("negative feedback must go to the curator.")

    def _check_useful(self) -> None:
        if self.status is not FeedbackStatus.NOT_APPLICABLE:
            raise DomainValidationError("useful feedback is not reviewed.")
        if self.question or self.answer:
            raise DomainValidationError("useful feedback keeps no conversation text.")

    @classmethod
    def submit(
        cls,
        *,
        id: str,
        message_id: str,
        conversation_id: str,
        assistant_id: str,
        user_id: str,
        rating: FeedbackRating,
        comment: str | None,
        question: str | None,
        answer: str,
        cited_documents: tuple[str, ...],
        now: datetime,
    ) -> MessageFeedback:
        negative = FeedbackRating(rating) is FeedbackRating.NOT_USEFUL
        return cls(
            id=id,
            message_id=message_id,
            conversation_id=conversation_id,
            assistant_id=assistant_id,
            user_id=user_id,
            rating=rating,
            comment=comment,
            question=question if negative else None,
            answer=answer if negative else None,
            cited_documents=cited_documents if negative else (),
            status=FeedbackStatus.PENDING if negative else FeedbackStatus.NOT_APPLICABLE,
            created_at=now,
            updated_at=now,
        )

    def resubmit(self, newer: MessageFeedback) -> MessageFeedback:
        """Nova avaliacao da mesma mensagem: mantem o id e a data de criacao."""
        if self.status in (FeedbackStatus.VALIDATED, FeedbackStatus.DISCARDED):
            raise InvalidFeedbackStateError(
                "feedback already reviewed by the curator cannot be changed."
            )
        return replace(newer, id=self.id, created_at=self.created_at)

    def validate(
        self,
        review: FeedbackReview,
        *,
        reviewer: str,
        now: datetime,
    ) -> MessageFeedback:
        self._require_pending()
        if not self.question:
            raise InvalidFeedbackStateError("feedback has no question to export.")
        return replace(
            self,
            status=FeedbackStatus.VALIDATED,
            review=review,
            reviewed_by=reviewer,
            reviewed_at=now,
            updated_at=now,
        )

    def discard(self, *, reviewer: str, now: datetime) -> MessageFeedback:
        self._require_pending()
        return replace(
            self,
            status=FeedbackStatus.DISCARDED,
            reviewed_by=reviewer,
            reviewed_at=now,
            updated_at=now,
        )

    def to_evaluation_item(self) -> EvaluationItem:
        """RN-33: so o item validado pelo curador entra no conjunto de referencia."""
        if self.status is not FeedbackStatus.VALIDATED or self.review is None:
            raise InvalidFeedbackStateError("only validated feedback can be exported.")
        return EvaluationItem(
            id=f"feedback-{self.id[:12]}",
            question=self.question or "",
            expected_answer=self.review.expected_answer,
            source_documents=self.review.source_documents,
            out_of_scope=self.review.out_of_scope,
            validated_by=self.reviewed_by,
        )

    def _require_pending(self) -> None:
        if self.status is not FeedbackStatus.PENDING:
            raise InvalidFeedbackStateError("only pending feedback can be reviewed.")


@dataclass(frozen=True, slots=True)
class FeedbackQuery:
    """Filtros da lista do curador; ``assistant_ids`` vazio nao devolve nada."""

    assistant_ids: frozenset[str] | None = None
    rating: FeedbackRating | None = FeedbackRating.NOT_USEFUL
    status: FeedbackStatus | None = FeedbackStatus.PENDING
    limit: int = 50
    offset: int = 0

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise DomainValidationError("feedback query limit must be positive.")
        if self.offset < 0:
            raise DomainValidationError("feedback query offset must not be negative.")
