"""Avaliacao das respostas e curadoria (SPEC-006: RF-61, RN-33)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from src.api.dependencies import (
    get_access_control,
    get_conversation_repository,
    get_current_user,
    get_feedback_repository,
    get_metrics,
)
from src.api.schemas import (
    FeedbackResponse,
    ReviewFeedbackRequest,
    SubmitFeedbackRequest,
)
from src.application.dto import FeedbackDTO
from src.application.services import AccessControl
from src.application.use_cases import (
    ExportFeedbackInput,
    ExportValidatedFeedbackUseCase,
    FeedbackNotFoundError,
    ListFeedbackInput,
    ListFeedbackUseCase,
    MessageNotFoundError,
    ReviewFeedbackInput,
    ReviewFeedbackUseCase,
    SubmitFeedbackInput,
    SubmitFeedbackUseCase,
)
from src.domain import (
    AuthenticatedUser,
    ConversationRepository,
    DomainValidationError,
    FeedbackRepository,
    MetricsRecorder,
)

router = APIRouter(tags=["feedback"], dependencies=[Depends(get_current_user)])


@router.post(
    "/messages/{message_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_feedback(
    message_id: str,
    payload: SubmitFeedbackRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    conversation_repository: ConversationRepository = Depends(
        get_conversation_repository
    ),
    feedback_repository: FeedbackRepository = Depends(get_feedback_repository),
    metrics: MetricsRecorder = Depends(get_metrics),
) -> FeedbackResponse:
    """So quem fez a pergunta avalia; mensagem alheia responde 404 (RN-24)."""
    use_case = SubmitFeedbackUseCase(
        conversation_repository=conversation_repository,
        feedback_repository=feedback_repository,
        access_control=access_control,
        metrics=metrics,
    )
    try:
        result = use_case.execute(
            SubmitFeedbackInput(
                user=user,
                message_id=message_id,
                rating=payload.rating.value,
                comment=payload.comment,
            )
        )
    except MessageNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "message not found") from exc
    except DomainValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return _response(result)


@router.get("/feedback", response_model=list[FeedbackResponse])
def list_feedback(
    assistant_id: str | None = Query(default=None),
    feedback_status: str | None = Query(
        default="pendente",
        alias="status",
        pattern="^(pendente|validado|descartado)$",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    feedback_repository: FeedbackRepository = Depends(get_feedback_repository),
) -> list[FeedbackResponse]:
    """Avaliacoes negativas dos assistentes que o curador cura."""
    items = ListFeedbackUseCase(
        feedback_repository=feedback_repository,
        access_control=access_control,
    ).execute(
        ListFeedbackInput(
            user=user,
            assistant_id=assistant_id,
            status=feedback_status,
            limit=limit,
            offset=offset,
        )
    )
    return [_response(item) for item in items]


@router.post("/feedback/{feedback_id}/review", response_model=FeedbackResponse)
def review_feedback(
    feedback_id: str,
    payload: ReviewFeedbackRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    feedback_repository: FeedbackRepository = Depends(get_feedback_repository),
) -> FeedbackResponse:
    use_case = ReviewFeedbackUseCase(
        feedback_repository=feedback_repository,
        access_control=access_control,
    )
    try:
        result = use_case.execute(
            ReviewFeedbackInput(
                user=user,
                feedback_id=feedback_id,
                decision=payload.decision.value,
                expected_answer=payload.expected_answer,
                source_documents=tuple(payload.source_documents),
                out_of_scope=payload.out_of_scope,
            )
        )
    except FeedbackNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "feedback not found") from exc
    except DomainValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return _response(result)


@router.get("/feedback/export")
def export_feedback(
    assistant_id: str = Query(min_length=1),
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    feedback_repository: FeedbackRepository = Depends(get_feedback_repository),
) -> Response:
    """JSONL no formato de ``tests/evaluation/datasets`` (SPEC-001)."""
    items = ExportValidatedFeedbackUseCase(
        feedback_repository=feedback_repository,
        access_control=access_control,
    ).execute(ExportFeedbackInput(user=user, assistant_id=assistant_id))
    lines = [
        json.dumps(
            {
                "id": item.id,
                "question": item.question,
                "expected_answer": item.expected_answer,
                "source_documents": list(item.source_documents),
                "out_of_scope": item.out_of_scope,
                "validated_by": item.validated_by,
            },
            ensure_ascii=False,
        )
        for item in items
    ]
    return Response(
        content="".join(f"{line}\n" for line in lines),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f'attachment; filename="feedback-{assistant_id}.jsonl"'
        },
    )


def _response(item: FeedbackDTO) -> FeedbackResponse:
    return FeedbackResponse(
        id=item.id,
        message_id=item.message_id,
        conversation_id=item.conversation_id,
        assistant_id=item.assistant_id,
        rating=item.rating,
        comment=item.comment,
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at,
        question=item.question,
        answer=item.answer,
        cited_documents=list(item.cited_documents),
        expected_answer=item.expected_answer,
        source_documents=list(item.source_documents),
        out_of_scope=item.out_of_scope,
        reviewed_by=item.reviewed_by,
        reviewed_at=item.reviewed_at,
    )
