from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_assistant_repository, get_conversation_repository
from src.api.schemas import (
    AddMessageRequest,
    ConversationDetailResponse,
    ConversationResponse,
    CreateConversationRequest,
    MessageResponse,
)
from src.application.use_cases import RegisterConversationInput, RegisterConversationUseCase
from src.domain import (
    AssistantId,
    ChatMessage,
    ConversationId,
    DomainValidationError,
    MessageId,
    MessageRole,
)
from src.infrastructure.database import PostgresAssistantRepository, PostgresConversationRepository

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: CreateConversationRequest,
    conversation_repository: PostgresConversationRepository = Depends(get_conversation_repository),
    assistant_repository: PostgresAssistantRepository = Depends(get_assistant_repository),
) -> ConversationResponse:
    try:
        assistant_id = AssistantId(payload.assistant_id)
    except DomainValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    assistant = assistant_repository.get_by_id(assistant_id)
    if assistant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="assistant not found")

    use_case = RegisterConversationUseCase(repository=conversation_repository)
    try:
        result = use_case.execute(RegisterConversationInput(assistant_id=assistant_id.value))
    except DomainValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ConversationResponse(
        id=result.conversation.id,
        assistant_id=result.conversation.assistant_id,
        created_at=result.conversation.created_at,
        updated_at=result.conversation.updated_at,
        message_count=result.conversation.message_count,
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: str,
    repository: PostgresConversationRepository = Depends(get_conversation_repository),
) -> ConversationDetailResponse:
    try:
        conversation_ref = ConversationId(conversation_id)
    except DomainValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    conversation = repository.get_by_id(conversation_ref)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found")
    return ConversationDetailResponse(
        id=conversation.id.value,
        assistant_id=conversation.assistant_id.value,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            MessageResponse(
                id=message.id.value,
                conversation_id=message.conversation_id.value,
                role=message.role.value,
                content=message.content,
                created_at=message.created_at,
            )
            for message in conversation.messages
        ],
    )


@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def add_message(
    conversation_id: str,
    payload: AddMessageRequest,
    repository: PostgresConversationRepository = Depends(get_conversation_repository),
) -> MessageResponse:
    try:
        conversation_ref = ConversationId(conversation_id)
    except DomainValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    conversation = repository.get_by_id(conversation_ref)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found")

    try:
        saved = repository.save_message(
            ChatMessage(
                id=MessageId(str(uuid4())),
                conversation_id=conversation_ref,
                role=MessageRole(payload.role.value),
                content=payload.content,
            )
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return MessageResponse(
        id=saved.id.value,
        conversation_id=saved.conversation_id.value,
        role=saved.role.value,
        content=saved.content,
        created_at=saved.created_at,
    )
