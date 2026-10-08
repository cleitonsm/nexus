from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from src.api.dependencies import (
    get_access_control,
    get_assistant_repository,
    get_current_user,
    get_document_repository,
    get_embedding_gateway,
    get_reindex_job_repository,
    get_reindex_runner,
    get_vector_store_gateway,
)
from src.api.schemas import IndexStatusResponse, ReindexJobResponse
from src.application.dto import ReindexJobDTO
from src.application.services import AccessControl
from src.application.use_cases import (
    GetIndexStatusInput,
    GetIndexStatusUseCase,
    StartReindexInput,
    StartReindexUseCase,
)
from src.domain import (
    AssistantId,
    AssistantRepository,
    AuthenticatedUser,
    DocumentRepository,
    DomainValidationError,
    EmbeddingGateway,
    ReindexInProgressError,
    ReindexJobRepository,
    VectorStoreGateway,
)

router = APIRouter(
    prefix="/assistants/{assistant_id}",
    tags=["index"],
    dependencies=[Depends(get_current_user)],
)


def _existing_assistant_id(
    assistant_id: str,
    assistant_repository: AssistantRepository,
) -> AssistantId:
    try:
        assistant_ref = AssistantId(assistant_id)
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    if assistant_repository.get_by_id(assistant_ref) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="assistant not found",
        )
    return assistant_ref


def _job_response(job: ReindexJobDTO) -> ReindexJobResponse:
    return ReindexJobResponse(**asdict(job))


@router.post(
    "/reindex",
    response_model=ReindexJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_reindex(
    assistant_id: str,
    background_tasks: BackgroundTasks,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    assistant_repository: AssistantRepository = Depends(get_assistant_repository),
    document_repository: DocumentRepository = Depends(get_document_repository),
    vector_store_gateway: VectorStoreGateway = Depends(get_vector_store_gateway),
    reindex_job_repository: ReindexJobRepository = Depends(
        get_reindex_job_repository
    ),
    reindex_runner: Callable[[str], None] = Depends(get_reindex_runner),
) -> ReindexJobResponse:
    assistant_ref = _existing_assistant_id(assistant_id, assistant_repository)
    use_case = StartReindexUseCase(
        document_repository=document_repository,
        vector_store_gateway=vector_store_gateway,
        reindex_job_repository=reindex_job_repository,
        access_control=access_control,
    )
    try:
        job = use_case.execute(
            StartReindexInput(user=user, assistant_id=assistant_ref.value)
        )
    except ReindexInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    background_tasks.add_task(reindex_runner, job.id)
    return _job_response(job)


@router.get("/index-status", response_model=IndexStatusResponse)
def get_index_status(
    assistant_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    assistant_repository: AssistantRepository = Depends(get_assistant_repository),
    document_repository: DocumentRepository = Depends(get_document_repository),
    vector_store_gateway: VectorStoreGateway = Depends(get_vector_store_gateway),
    embedding_gateway: EmbeddingGateway = Depends(get_embedding_gateway),
    reindex_job_repository: ReindexJobRepository = Depends(
        get_reindex_job_repository
    ),
) -> IndexStatusResponse:
    assistant_ref = _existing_assistant_id(assistant_id, assistant_repository)
    result = GetIndexStatusUseCase(
        document_repository=document_repository,
        vector_store_gateway=vector_store_gateway,
        embedding_gateway=embedding_gateway,
        reindex_job_repository=reindex_job_repository,
        access_control=access_control,
    ).execute(GetIndexStatusInput(user=user, assistant_id=assistant_ref.value))
    return IndexStatusResponse(
        assistant_id=result.assistant_id,
        embedding_model=result.embedding_model,
        pipeline_version=result.pipeline_version,
        collection_name=result.collection_name,
        outdated=result.outdated,
        documents_total=result.documents_total,
        documents_indexed=result.documents_indexed,
        documents_without_original=list(result.documents_without_original),
        last_reindex=(
            _job_response(result.last_reindex) if result.last_reindex else None
        ),
    )
