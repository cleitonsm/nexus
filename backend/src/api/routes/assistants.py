from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_assistant_repository, get_conversation_repository
from src.api.schemas import (
    AssistantResponse,
    ConversationHistoryResponse,
    CreateAssistantRequest,
)
from src.application.use_cases import (
    CreateAssistantInput,
    CreateAssistantUseCase,
    ListConversationsInput,
    ListConversationsUseCase,
    ListAssistantsUseCase,
)
from src.domain import AssistantId, DomainValidationError
from src.infrastructure.database import (
    PostgresAssistantRepository,
    PostgresConversationRepository,
)

router = APIRouter(prefix="/assistants", tags=["assistants"])


@router.post("", response_model=AssistantResponse, status_code=status.HTTP_201_CREATED)
def create_assistant(
    payload: CreateAssistantRequest,
    repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
) -> AssistantResponse:
    use_case = CreateAssistantUseCase(repository=repository)
    try:
        created = use_case.execute(
            CreateAssistantInput(
                name=payload.name,
                description=payload.description,
            )
        )
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return AssistantResponse(
        id=created.id,
        name=created.name,
        description=created.description,
        created_at=created.created_at,
    )


@router.get("", response_model=list[AssistantResponse])
def list_assistants(
    repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
) -> list[AssistantResponse]:
    use_case = ListAssistantsUseCase(repository=repository)
    assistants = use_case.execute()
    return [
        AssistantResponse(
            id=item.id,
            name=item.name,
            description=item.description,
            created_at=item.created_at,
        )
        for item in assistants
    ]


@router.get(
    "/{assistant_id}/conversations",
    response_model=list[ConversationHistoryResponse],
)
def list_assistant_conversations(
    assistant_id: str,
    assistant_repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
    conversation_repository: PostgresConversationRepository = Depends(
        get_conversation_repository
    ),
) -> list[ConversationHistoryResponse]:
    try:
        assistant_ref = AssistantId(assistant_id)
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    assistant = assistant_repository.get_by_id(assistant_ref)
    if assistant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="assistant not found",
        )

    use_case = ListConversationsUseCase(repository=conversation_repository)
    result = use_case.execute(
        ListConversationsInput(assistant_id=assistant_ref.value)
    )
    return [
        ConversationHistoryResponse(
            id=conversation.id,
            assistant_id=conversation.assistant_id,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=conversation.message_count,
        )
        for conversation in result.conversations
    ]
