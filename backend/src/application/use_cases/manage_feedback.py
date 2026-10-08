"""Avaliacao das respostas e curadoria (SPEC-006: RF-61, RN-33)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from src.application.dto import FeedbackDTO
from src.application.services import AccessControl
from src.domain import (
    AuditAction,
    AuditResource,
    AuthenticatedUser,
    ChatMessage,
    ConversationRepository,
    EvaluationItem,
    FeedbackQuery,
    FeedbackRating,
    FeedbackRepository,
    FeedbackReview,
    FeedbackStatus,
    MessageFeedback,
    MessageRole,
    MetricsRecorder,
    NoopMetrics,
)


class MessageNotFoundError(ValueError):
    """Mensagem inexistente ou de conversa de outra pessoa (RN-24)."""


class FeedbackNotFoundError(ValueError):
    pass


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class SubmitFeedbackInput:
    user: AuthenticatedUser
    message_id: str
    rating: str
    comment: str | None = None


class SubmitFeedbackUseCase:
    """So quem fez a pergunta avalia a resposta; a ultima avaliacao vale."""

    def __init__(
        self,
        *,
        conversation_repository: ConversationRepository,
        feedback_repository: FeedbackRepository,
        access_control: AccessControl,
        clock: Callable[[], datetime] = _utc_now,
        metrics: MetricsRecorder | None = None,
    ) -> None:
        self._conversations = conversation_repository
        self._feedback = feedback_repository
        self._access = access_control
        self._clock = clock
        self._metrics = metrics or NoopMetrics()

    def execute(self, data: SubmitFeedbackInput) -> FeedbackDTO:
        rating = FeedbackRating(data.rating)
        message = self._conversations.get_message(data.message_id)
        if message is None or message.role is not MessageRole.ASSISTANT:
            raise MessageNotFoundError("message not found.")
        conversation = self._conversations.get_by_id(message.conversation_id)
        if conversation is None or not self._access.owns_conversation(
            data.user, conversation.owner_user_id
        ):
            raise MessageNotFoundError("message not found.")

        history = self._conversations.list_messages(conversation.id)
        submitted = MessageFeedback.submit(
            id=str(uuid4()),
            message_id=message.id.value,
            conversation_id=conversation.id.value,
            assistant_id=conversation.assistant_id.value,
            user_id=data.user.id,
            rating=rating,
            comment=data.comment,
            question=_question_before(history, message),
            answer=message.content,
            cited_documents=tuple(
                dict.fromkeys(
                    item.source_name or item.document_id.value
                    for item in message.citations
                )
            ),
            now=self._clock(),
        )
        previous = self._feedback.get_by_message(message.id.value, data.user.id)
        feedback = previous.resubmit(submitted) if previous else submitted
        saved = self._feedback.save(feedback)
        self._metrics.increment(
            "nexus_feedback_total", labels={"rating": saved.rating.value}
        )
        self._access.audit(
            data.user,
            AuditAction.FEEDBACK_SUBMITTED,
            resource_type=AuditResource.MESSAGE,
            resource_id=message.id.value,
            details={
                "assistant_id": saved.assistant_id,
                "conversation_id": saved.conversation_id,
                "rating": saved.rating.value,
                "has_comment": saved.comment is not None,
            },
        )
        return FeedbackDTO.for_author(saved)


def _question_before(history: list[ChatMessage], answer: ChatMessage) -> str | None:
    """A pergunta e a mensagem do usuario imediatamente anterior a resposta."""
    question: str | None = None
    for message in history:
        if message.id == answer.id:
            return question
        if message.role is MessageRole.USER:
            question = message.content
    return question


@dataclass(frozen=True, slots=True)
class ListFeedbackInput:
    user: AuthenticatedUser
    assistant_id: str | None = None
    status: str | None = FeedbackStatus.PENDING.value
    limit: int = 50
    offset: int = 0


class ListFeedbackUseCase:
    """RN-33: avaliacoes negativas dos assistentes que o curador cura."""

    def __init__(
        self,
        *,
        feedback_repository: FeedbackRepository,
        access_control: AccessControl,
    ) -> None:
        self._feedback = feedback_repository
        self._access = access_control

    def execute(self, data: ListFeedbackInput) -> list[FeedbackDTO]:
        scope = self._access.require_curation(data.user, AuditAction.FEEDBACK_CONSULTED)
        assistant_ids = _narrow_scope(scope, data.assistant_id)
        items = self._feedback.list_feedback(
            FeedbackQuery(
                assistant_ids=assistant_ids,
                rating=FeedbackRating.NOT_USEFUL,
                status=FeedbackStatus(data.status) if data.status else None,
                limit=data.limit,
                offset=data.offset,
            )
        )
        return [FeedbackDTO.for_curator(item) for item in items]


@dataclass(frozen=True, slots=True)
class ReviewFeedbackInput:
    user: AuthenticatedUser
    feedback_id: str
    decision: str
    expected_answer: str | None = None
    source_documents: tuple[str, ...] = ()
    out_of_scope: bool = False


class ReviewFeedbackUseCase:
    """O curador valida (vira item de referencia) ou descarta a avaliacao."""

    def __init__(
        self,
        *,
        feedback_repository: FeedbackRepository,
        access_control: AccessControl,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._feedback = feedback_repository
        self._access = access_control
        self._clock = clock

    def execute(self, data: ReviewFeedbackInput) -> FeedbackDTO:
        decision = FeedbackStatus(data.decision)
        if decision not in (FeedbackStatus.VALIDATED, FeedbackStatus.DISCARDED):
            raise ValueError("decision must be 'validado' or 'descartado'.")
        scope = self._access.require_curation(data.user, AuditAction.FEEDBACK_REVIEWED)
        feedback = self._feedback.get_by_id(data.feedback_id)
        if feedback is None or not _in_scope(scope, feedback.assistant_id):
            raise FeedbackNotFoundError("feedback not found.")
        now = self._clock()
        if decision is FeedbackStatus.VALIDATED:
            reviewed = feedback.validate(
                FeedbackReview(
                    expected_answer=data.expected_answer,
                    source_documents=data.source_documents,
                    out_of_scope=data.out_of_scope,
                ),
                reviewer=data.user.name,
                now=now,
            )
        else:
            reviewed = feedback.discard(reviewer=data.user.name, now=now)
        saved = self._feedback.save(reviewed)
        self._access.audit(
            data.user,
            AuditAction.FEEDBACK_REVIEWED,
            resource_type=AuditResource.FEEDBACK,
            resource_id=saved.id,
            details={"assistant_id": saved.assistant_id, "decision": decision.value},
        )
        return FeedbackDTO.for_curator(saved)


@dataclass(frozen=True, slots=True)
class ExportFeedbackInput:
    user: AuthenticatedUser
    assistant_id: str


class ExportValidatedFeedbackUseCase:
    """Itens validados no formato do conjunto de referencia da SPEC-001."""

    MAX_ITEMS = 1000

    def __init__(
        self,
        *,
        feedback_repository: FeedbackRepository,
        access_control: AccessControl,
    ) -> None:
        self._feedback = feedback_repository
        self._access = access_control

    def execute(self, data: ExportFeedbackInput) -> list[EvaluationItem]:
        scope = self._access.require_curation(data.user, AuditAction.FEEDBACK_EXPORTED)
        assistant_ids = _narrow_scope(scope, data.assistant_id)
        items = self._feedback.list_feedback(
            FeedbackQuery(
                assistant_ids=assistant_ids,
                rating=FeedbackRating.NOT_USEFUL,
                status=FeedbackStatus.VALIDATED,
                limit=self.MAX_ITEMS,
            )
        )
        exported = [item.to_evaluation_item() for item in items]
        self._access.audit(
            data.user,
            AuditAction.FEEDBACK_EXPORTED,
            resource_type=AuditResource.ASSISTANT,
            resource_id=data.assistant_id,
            details={"assistant_id": data.assistant_id, "items": len(exported)},
        )
        return exported


def _in_scope(scope: frozenset[str] | None, assistant_id: str) -> bool:
    return scope is None or assistant_id in scope


def _narrow_scope(
    scope: frozenset[str] | None,
    assistant_id: str | None,
) -> frozenset[str] | None:
    """Filtro pedido dentro do alcance do curador; fora dele, lista vazia."""
    if not assistant_id:
        return scope
    if not _in_scope(scope, assistant_id):
        return frozenset()
    return frozenset({assistant_id})
