from __future__ import annotations

import contextvars
import json
import logging
from collections.abc import Iterator
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.dependencies import (
    get_access_control,
    get_answer_generator,
    get_assistant_repository,
    get_context_retriever,
    get_conversation_repository,
    get_current_user,
    get_document_repository,
    get_metrics,
    get_session,
    get_token_counter,
    get_tracer,
    get_usage_governance,
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
from src.application.dto import ChatStreamEvent, ChatTurnResult, MessageDTO
from src.application.services import (
    AccessControl,
    ContextRetriever,
    GroundedAnswerGenerator,
    UsageGovernance,
)
from src.application.use_cases import (
    AddMessageInput,
    ArchivedConversationInput,
    DeleteArchivedConversationUseCase,
    GetArchivedConversationUseCase,
    ListArchivedConversationsUseCase,
    AddMessageUseCase,
    ChatWithAssistantInput,
    ChatWithAssistantUseCase,
    ConversationNotFoundError,
    ConversationRefInput,
    DeleteConversationUseCase,
    GetConversationUseCase,
    RegisterConversationInput,
    RegisterConversationUseCase,
)
from src.domain import (
    AssistantId,
    AuthenticatedUser,
    DocumentRepository,
    DomainValidationError,
    IndexOutdatedError,
    MetricsRecorder,
    TokenCounter,
    Tracer,
)
from src.infrastructure.database import (
    PostgresAssistantRepository,
    PostgresConversationRepository,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
    dependencies=[Depends(get_current_user)],
)

# PC-D5: conversas anteriores a autenticacao, so para o administrador.
archived_router = APIRouter(
    prefix="/admin/archived-conversations",
    tags=["admin"],
    dependencies=[Depends(get_current_user)],
)


def _not_found(exc: Exception) -> HTTPException:
    """Conversa inexistente e conversa de outra pessoa respondem igual (RN-24)."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="conversation not found",
    )


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: CreateConversationRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
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

    use_case = RegisterConversationUseCase(conversation_repository, access_control)
    try:
        result = use_case.execute(
            RegisterConversationInput(user=user, assistant_id=assistant_id.value)
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
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    repository: PostgresConversationRepository = Depends(get_conversation_repository),
    document_repository: DocumentRepository = Depends(get_document_repository),
) -> ConversationDetailResponse:
    use_case = GetConversationUseCase(repository, access_control, document_repository)
    try:
        conversation = use_case.execute(
            ConversationRefInput(user=user, conversation_id=conversation_id)
        )
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ConversationNotFoundError as exc:
        raise _not_found(exc) from exc
    removed = use_case.removed_sources(conversation)
    return ConversationDetailResponse(
        id=conversation.id.value,
        assistant_id=conversation.assistant_id.value,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            _message_response(
                MessageDTO.from_entity(message, removed_documents=removed)
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
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    repository: PostgresConversationRepository = Depends(get_conversation_repository),
) -> Response:
    use_case = DeleteConversationUseCase(repository, access_control)
    try:
        use_case.execute(
            ConversationRefInput(user=user, conversation_id=conversation_id)
        )
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ConversationNotFoundError as exc:
        raise _not_found(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_message(
    conversation_id: str,
    payload: AddMessageRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    repository: PostgresConversationRepository = Depends(get_conversation_repository),
) -> MessageResponse:
    use_case = AddMessageUseCase(repository, access_control)
    try:
        saved = use_case.execute(
            AddMessageInput(
                user=user,
                conversation_id=conversation_id,
                role=payload.role.value,
                content=payload.content,
            )
        )
    except ConversationNotFoundError as exc:
        raise _not_found(exc) from exc
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return _message_response(saved)


@router.post(
    "/{conversation_id}/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_201_CREATED,
)
def chat_with_assistant(
    conversation_id: str,
    payload: ChatRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    assistant_repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
    conversation_repository: PostgresConversationRepository = Depends(
        get_conversation_repository
    ),
    context_retriever: ContextRetriever = Depends(get_context_retriever),
    answer_generator: GroundedAnswerGenerator = Depends(get_answer_generator),
    token_counter: TokenCounter = Depends(get_token_counter),
    usage_governance: UsageGovernance | None = Depends(get_usage_governance),
    tracer: Tracer = Depends(get_tracer),
    metrics: MetricsRecorder = Depends(get_metrics),
) -> ChatResponse:
    """Resposta completa de uma vez; mantida para testes e para a avaliacao."""
    use_case = ChatWithAssistantUseCase(
        assistant_repository=assistant_repository,
        conversation_repository=conversation_repository,
        context_retriever=context_retriever,
        answer_generator=answer_generator,
        token_counter=token_counter,
        access_control=access_control,
        usage_governance=usage_governance,
        tracer=tracer,
        metrics=metrics,
    )
    try:
        result = use_case.execute(_chat_input(user, conversation_id, payload))
    except (ConversationNotFoundError, IndexOutdatedError, ValueError, RuntimeError) as exc:
        raise _chat_error(exc) from exc
    return _chat_response(result)


@router.post(
    "/{conversation_id}/chat/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
def chat_with_assistant_stream(
    conversation_id: str,
    payload: ChatRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    access_control: AccessControl = Depends(get_access_control),
    assistant_repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
    conversation_repository: PostgresConversationRepository = Depends(
        get_conversation_repository
    ),
    context_retriever: ContextRetriever = Depends(get_context_retriever),
    answer_generator: GroundedAnswerGenerator = Depends(get_answer_generator),
    token_counter: TokenCounter = Depends(get_token_counter),
    usage_governance: UsageGovernance | None = Depends(get_usage_governance),
    tracer: Tracer = Depends(get_tracer),
    metrics: MetricsRecorder = Depends(get_metrics),
) -> StreamingResponse:
    """RF-58: Server-Sent Events.

    Antes do primeiro byte, os erros de entrada respondem com o status HTTP
    de sempre (404, 403, 409, 422, 429). Depois, chegam como evento
    ``error``. Eventos: ``delta`` (texto novo), ``replace`` (texto final
    diferente do transmitido, como o fallback), ``done`` (resposta completa
    com as citacoes, no formato da rota sem streaming) e ``error``.
    """
    use_case = ChatWithAssistantUseCase(
        assistant_repository=assistant_repository,
        conversation_repository=conversation_repository,
        context_retriever=context_retriever,
        answer_generator=answer_generator,
        token_counter=token_counter,
        access_control=access_control,
        usage_governance=usage_governance,
        tracer=tracer,
        metrics=metrics,
    )
    try:
        events = use_case.start_stream(_chat_input(user, conversation_id, payload))
    except (ConversationNotFoundError, IndexOutdatedError, ValueError, RuntimeError) as exc:
        raise _chat_error(exc) from exc
    return StreamingResponse(
        _server_sent_events(events, session),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # O Nginx entrega cada parte assim que ela chega (CT-55).
            "X-Accel-Buffering": "no",
        },
    )


def _chat_input(
    user: AuthenticatedUser,
    conversation_id: str,
    payload: ChatRequest,
) -> ChatWithAssistantInput:
    return ChatWithAssistantInput(
        user=user,
        conversation_id=conversation_id,
        question=payload.question,
        top_k=payload.top_k,
    )


def _chat_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ConversationNotFoundError):
        return _not_found(exc)
    if isinstance(exc, IndexOutdatedError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


def _in_one_context(events: Iterator[ChatStreamEvent]) -> Iterator[ChatStreamEvent]:
    """Avanca o gerador sempre no mesmo contexto.

    O Starlette consome geradores sincronos numa thread por parte, cada vez
    com uma copia nova do contexto. Sem isto, o trecho atual do rastreamento
    (``ContextVar``) se perderia entre as partes e as etapas seguintes do
    grafo sairiam do rastreamento da pergunta (RF-56).
    """
    context = contextvars.copy_context()
    try:
        while True:
            try:
                event = context.run(next, events)
            except StopIteration:
                return
            yield event
    finally:
        close = getattr(events, "close", None)
        if close is not None:
            context.run(close)


def _server_sent_events(
    events: Iterator[ChatStreamEvent],
    session: Session,
) -> Iterator[str]:
    try:
        for event in _in_one_context(events):
            if event.kind == "done" and event.result is not None:
                data = jsonable_encoder(_chat_response(event.result))
            else:
                data = {"text": event.text}
            yield _sse(event.kind, data)
    except Exception as exc:  # noqa: BLE001 - o status HTTP ja foi enviado
        error = _chat_error(exc) if isinstance(exc, (ValueError, RuntimeError)) else None
        logger.warning(
            "chat.stream.failed",
            extra={"error_type": type(exc).__name__},
        )
        yield _sse(
            "error",
            {
                "status": error.status_code if error else 500,
                "detail": error.detail if error else "internal error",
            },
        )
    finally:
        session.close()


def _sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _chat_response(result: ChatTurnResult) -> ChatResponse:
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
                document_available=item.document_available,
            )
            for item in message.citations
        ],
    )


@archived_router.get("", response_model=list[ConversationResponse])
def list_archived_conversations(
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    repository: PostgresConversationRepository = Depends(get_conversation_repository),
) -> list[ConversationResponse]:
    items = ListArchivedConversationsUseCase(repository, access_control).execute(user)
    return [ConversationResponse(**asdict(item)) for item in items]


@archived_router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_archived_conversation(
    conversation_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    repository: PostgresConversationRepository = Depends(get_conversation_repository),
    document_repository: DocumentRepository = Depends(get_document_repository),
) -> ConversationDetailResponse:
    try:
        conversation = GetArchivedConversationUseCase(repository, access_control).execute(
            ArchivedConversationInput(user=user, conversation_id=conversation_id)
        )
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ConversationNotFoundError as exc:
        raise _not_found(exc) from exc
    removed = GetConversationUseCase(
        repository, access_control, document_repository
    ).removed_sources(conversation)
    return ConversationDetailResponse(
        id=conversation.id.value,
        assistant_id=conversation.assistant_id.value,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            _message_response(
                MessageDTO.from_entity(message, removed_documents=removed)
            )
            for message in conversation.messages
        ],
    )


@archived_router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_archived_conversation(
    conversation_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    repository: PostgresConversationRepository = Depends(get_conversation_repository),
) -> Response:
    try:
        DeleteArchivedConversationUseCase(repository, access_control).execute(
            ArchivedConversationInput(user=user, conversation_id=conversation_id)
        )
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ConversationNotFoundError as exc:
        raise _not_found(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
