from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.api.dependencies import (
    get_access_control,
    get_assistant_repository,
    get_conversation_repository,
    get_current_user,
    get_default_llm_gateway,
    get_document_repository,
    get_file_storage,
    get_reindex_job_repository,
    get_vector_store_gateway,
)
from src.api.schemas import (
    AssistantResponse,
    ConversationHistoryResponse,
    CreateAssistantRequest,
    GroupsRequest,
    GroupsResponse,
    InferAssistantRequest,
    InferAssistantResponse,
    UpdateAssistantRequest,
)
from src.application.dto import AssistantDTO
from src.application.services import AccessControl
from src.application.use_cases import (
    AssistantNotFoundError,
    CreateAssistantInput,
    CreateAssistantUseCase,
    DeleteAssistantInput,
    DeleteAssistantUseCase,
    InferAssistantInput,
    InferAssistantUseCase,
    ListAssistantsUseCase,
    ListConversationsInput,
    ListConversationsUseCase,
    SetAssistantGroupsInput,
    SetAssistantGroupsUseCase,
    UpdateAssistantInput,
    UpdateAssistantUseCase,
)
from src.domain import (
    AssistantId,
    AssistantProfileValidationError,
    AuthenticatedUser,
    DocumentFileStorage,
    DomainValidationError,
    LLMGateway,
    ReindexInProgressError,
    VectorStoreGateway,
)
from src.infrastructure.database import (
    PostgresAssistantRepository,
    PostgresConversationRepository,
    PostgresDocumentRepository,
    PostgresReindexJobRepository,
)

router = APIRouter(
    prefix="/assistants",
    tags=["assistants"],
    dependencies=[Depends(get_current_user)],
)


def _assistant_response(item: AssistantDTO) -> AssistantResponse:
    return AssistantResponse(
        id=item.id,
        name=item.name,
        description=item.description,
        initial_prompt=item.initial_prompt,
        created_at=item.created_at,
        groups=list(item.groups),
    )


@router.post("", response_model=AssistantResponse, status_code=status.HTTP_201_CREATED)
def create_assistant(
    payload: CreateAssistantRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
) -> AssistantResponse:
    use_case = CreateAssistantUseCase(repository, access_control)
    try:
        created = use_case.execute(
            CreateAssistantInput(
                user=user,
                name=payload.name,
                description=payload.description,
                initial_prompt=payload.initial_prompt,
            )
        )
    except AssistantProfileValidationError:
        raise  # SPEC-017: 422 com o ``code`` da regra (api/errors.py).
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return _assistant_response(created)


@router.get("", response_model=list[AssistantResponse])
def list_assistants(
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
) -> list[AssistantResponse]:
    assistants = ListAssistantsUseCase(repository, access_control).execute(user)
    return [_assistant_response(item) for item in assistants]


@router.post("/infer", response_model=InferAssistantResponse)
def infer_assistant(
    payload: InferAssistantRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
    # SPEC-013: credencial padrao (sem assistente escolhido ainda).
    llm_gateway: LLMGateway = Depends(get_default_llm_gateway),
) -> InferAssistantResponse:
    # So concorrem os assistentes que o usuario pode usar (RF-42), com o prompt
    # mesmo para quem nao o le na listagem (SPEC-017, D5).
    assistants = ListAssistantsUseCase(repository, access_control).inference_catalog(user)
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
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
    vector_store_gateway: VectorStoreGateway = Depends(get_vector_store_gateway),
    document_repository: PostgresDocumentRepository = Depends(
        get_document_repository
    ),
    file_storage: DocumentFileStorage = Depends(get_file_storage),
    reindex_job_repository: PostgresReindexJobRepository = Depends(
        get_reindex_job_repository
    ),
) -> Response:
    """SPEC-014: exclui o assistente, a base vetorial e os originais."""
    use_case = DeleteAssistantUseCase(
        assistant_repository=repository,
        vector_store_gateway=vector_store_gateway,
        access_control=access_control,
        document_repository=document_repository,
        file_storage=file_storage,
        reindex_job_repository=reindex_job_repository,
    )
    try:
        use_case.execute(DeleteAssistantInput(user=user, assistant_id=assistant_id))
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except AssistantNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="assistant not found",
        ) from exc
    except ReindexInProgressError as exc:
        # RN-45 (SPEC-014): nada foi apagado.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "reindex_in_progress",
                "message": (
                    "Há uma reindexação em andamento neste assistente. "
                    "Aguarde a conclusão para excluí-lo."
                ),
            },
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{assistant_id}", response_model=AssistantResponse)
def update_assistant(
    assistant_id: str,
    payload: UpdateAssistantRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
) -> AssistantResponse:
    """SPEC-017: altera nome, descricao e prompt (RF-108).

    403 para quem nao edita o assistente, exista ele ou nao (RN-52); 404 so
    para quem pode editar; 422 com o ``code`` da RN-51.
    """
    use_case = UpdateAssistantUseCase(repository, access_control)
    try:
        updated = use_case.execute(
            UpdateAssistantInput(
                user=user,
                assistant_id=assistant_id,
                name=payload.name,
                description=payload.description,
                initial_prompt=payload.initial_prompt,
            )
        )
    except AssistantProfileValidationError:
        raise
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except AssistantNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "assistant_not_found", "message": "assistant not found"},
        ) from exc
    return _assistant_response(updated)


@router.put("/{assistant_id}/groups", response_model=GroupsResponse)
def set_assistant_groups(
    assistant_id: str,
    payload: GroupsRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
) -> GroupsResponse:
    """RF-42: define os grupos do Keycloak que usam o assistente."""
    use_case = SetAssistantGroupsUseCase(
        assistant_repository=repository,
        access_control=access_control,
    )
    try:
        groups = use_case.execute(
            SetAssistantGroupsInput(
                user=user,
                assistant_id=assistant_id,
                groups=tuple(payload.groups),
            )
        )
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except AssistantNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="assistant not found",
        ) from exc
    return GroupsResponse(groups=list(groups))


@router.get(
    "/{assistant_id}/conversations",
    response_model=list[ConversationHistoryResponse],
)
def list_assistant_conversations(
    assistant_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
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

    use_case = ListConversationsUseCase(conversation_repository, access_control)
    result = use_case.execute(
        ListConversationsInput(user=user, assistant_id=assistant_ref.value)
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
