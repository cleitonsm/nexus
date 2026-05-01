from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.api.dependencies import (
    get_assistant_repository,
    get_conversation_repository,
    get_embedding_gateway,
    get_llm_gateway,
    get_vector_store_gateway,
)
from src.api.schemas import (
    AddMessageRequest,
    ChatRequest,
    ChatResponse,
    ConversationDetailResponse,
    ConversationResponse,
    CreateConversationRequest,
    MessageResponse,
)
from src.application.use_cases import (
    ChatWithAssistantInput,
    ChatWithAssistantUseCase,
    ConversationNotFoundError,
    RegisterConversationInput,
    RegisterConversationUseCase,
)
from src.domain import (
    AssistantId,
    ChatMessage,
    ConversationId,
    DomainValidationError,
    EmbeddingGateway,
    LLMGateway,
    MessageId,
    MessageRole,
    VectorStoreGateway,
)
from src.infrastructure.database import (
    PostgresAssistantRepository,
    PostgresConversationRepository,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: CreateConversationRequest,
    conversation_repository: PostgresConversationRepository = Depends(
        get_conversation_repository
    ),
    assistant_repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
) -> ConversationResponse:
    try:
        assistant_id = AssistantId(payload.assistant_id)
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    assistant = assistant_repository.get_by_id(assistant_id)
    if assistant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="assistant not found",
        )

    use_case = RegisterConversationUseCase(repository=conversation_repository)
    try:
        result = use_case.execute(
            RegisterConversationInput(assistant_id=assistant_id.value)
        )
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    conversation = repository.get_by_id(conversation_ref)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="conversation not found",
        )
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


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_conversation(
    conversation_id: str,
    repository: PostgresConversationRepository = Depends(get_conversation_repository),
) -> Response:
    try:
        conversation_ref = ConversationId(conversation_id)
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    deleted = repository.delete(conversation_ref)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="conversation not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_message(
    conversation_id: str,
    payload: AddMessageRequest,
    repository: PostgresConversationRepository = Depends(get_conversation_repository),
) -> MessageResponse:
    try:
        conversation_ref = ConversationId(conversation_id)
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    conversation = repository.get_by_id(conversation_ref)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="conversation not found",
        )

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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return MessageResponse(
        id=saved.id.value,
        conversation_id=saved.conversation_id.value,
        role=saved.role.value,
        content=saved.content,
        created_at=saved.created_at,
    )


@router.post(
    "/{conversation_id}/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_201_CREATED,
)
def chat_with_assistant(
    conversation_id: str,
    payload: ChatRequest,
    assistant_repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
    conversation_repository: PostgresConversationRepository = Depends(
        get_conversation_repository
    ),
    embedding_gateway: EmbeddingGateway = Depends(get_embedding_gateway),
    vector_store_gateway: VectorStoreGateway = Depends(get_vector_store_gateway),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
) -> ChatResponse:
    use_case = ChatWithAssistantUseCase(
        assistant_repository=assistant_repository,
        conversation_repository=conversation_repository,
        embedding_gateway=embedding_gateway,
        vector_store_gateway=vector_store_gateway,
        llm_gateway=llm_gateway,
    )
    try:
        result = use_case.execute(
            ChatWithAssistantInput(
                conversation_id=conversation_id,
                question=payload.question,
                top_k=payload.top_k,
            )
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return ChatResponse(
        conversation_id=result.conversation_id,
        assistant_id=result.assistant_id,
        user_message=MessageResponse(
            id=result.user_message.id,
            conversation_id=result.user_message.conversation_id,
            role=result.user_message.role,
            content=result.user_message.content,
            created_at=result.user_message.created_at,
        ),
        assistant_message=MessageResponse(
            id=result.assistant_message.id,
            conversation_id=result.assistant_message.conversation_id,
            role=result.assistant_message.role,
            content=result.assistant_message.content,
            created_at=result.assistant_message.created_at,
        ),
        used_context_chunks=result.used_context_chunks,
        fallback_used=result.fallback_used,
    )
