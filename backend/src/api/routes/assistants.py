from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.api.dependencies import (
    get_assistant_repository,
    get_conversation_repository,
    get_llm_gateway,
    get_vector_store_gateway,
)
from src.api.schemas import (
    AssistantResponse,
    ConversationHistoryResponse,
    CreateAssistantRequest,
    InferAssistantRequest,
    InferAssistantResponse,
)
from src.application.use_cases import (
    CreateAssistantInput,
    CreateAssistantUseCase,
    InferAssistantInput,
    InferAssistantUseCase,
    ListAssistantsUseCase,
    ListConversationsInput,
    ListConversationsUseCase,
)
from src.domain import (
    AssistantId,
    CollectionName,
    DomainValidationError,
    LLMGateway,
    VectorStoreGateway,
)
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
                initial_prompt=payload.initial_prompt,
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
        initial_prompt=created.initial_prompt,
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
            initial_prompt=item.initial_prompt,
            created_at=item.created_at,
        )
        for item in assistants
    ]


@router.post("/infer", response_model=InferAssistantResponse)
def infer_assistant(
    payload: InferAssistantRequest,
    repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
) -> InferAssistantResponse:
    assistants = ListAssistantsUseCase(repository=repository).execute()
    result = InferAssistantUseCase(llm_gateway=llm_gateway).execute(
        InferAssistantInput(
            question=payload.question,
            assistants=[
                {
                    "id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "initial_prompt": item.initial_prompt,
                }
                for item in assistants
            ],
        )
    )
    return InferAssistantResponse(assistant_id=result.assistant_id)


@router.delete(
    "/{assistant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_assistant(
    assistant_id: str,
    repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
    vector_store_gateway: VectorStoreGateway = Depends(get_vector_store_gateway),
) -> Response:
    try:
        assistant_ref = AssistantId(assistant_id)
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    deleted = repository.delete(assistant_ref)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="assistant not found",
        )
    vector_store_gateway.delete_collection(
        CollectionName.from_assistant_id(assistant_ref)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
            name=conversation.name,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=conversation.message_count,
        )
        for conversation in result.conversations
    ]
