from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.api.dependencies import (
    get_answer_generator,
    get_assistant_repository,
    get_context_retriever,
    get_conversation_repository,
    get_token_counter,
)
from src.api.schemas import (
    AddMessageRequest,
    ChatRequest,
    ChatResponse,
    CitationResponse,
    ConversationDetailResponse,
    ConversationResponse,
    CreateConversationRequest,
    MessageResponse,
)
from src.application.dto import MessageDTO
from src.application.services import ContextRetriever, GroundedAnswerGenerator
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
    IndexOutdatedError,
    MessageId,
    MessageRole,
    TokenCounter,
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
        name=result.conversation.name,
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
            _message_response(MessageDTO.from_entity(message))
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

    return _message_response(MessageDTO.from_entity(saved))


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
    context_retriever: ContextRetriever = Depends(get_context_retriever),
    answer_generator: GroundedAnswerGenerator = Depends(get_answer_generator),
    token_counter: TokenCounter = Depends(get_token_counter),
) -> ChatResponse:
    use_case = ChatWithAssistantUseCase(
        assistant_repository=assistant_repository,
        conversation_repository=conversation_repository,
        context_retriever=context_retriever,
        answer_generator=answer_generator,
        token_counter=token_counter,
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
    except IndexOutdatedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
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

    assistant_message = _message_response(result.assistant_message)
    return ChatResponse(
        conversation_id=result.conversation_id,
        assistant_id=result.assistant_id,
        user_message=_message_response(result.user_message),
        assistant_message=assistant_message,
        used_context_chunks=result.used_context_chunks,
        fallback_used=result.fallback_used,
        citations=assistant_message.citations,
        rewritten_query=result.rewritten_query,
    )


def _message_response(message: MessageDTO) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
        citations=[
            CitationResponse(
                number=item.number,
                document_id=item.document_id,
                chunk_id=item.chunk_id,
                source_name=item.source_name,
                section_path=item.section_path,
                page=item.page,
                score=item.score,
                excerpt=item.excerpt,
            )
            for item in message.citations
        ],
    )
