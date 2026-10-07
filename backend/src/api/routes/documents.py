from __future__ import annotations

import json
import logging
from json import JSONDecodeError

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool

from src.api.dependencies import (
    get_assistant_repository,
    get_document_indexer,
    get_document_repository,
    get_file_storage,
    get_max_file_bytes,
    get_reindex_job_repository,
    get_vector_store_gateway,
)
from src.api.schemas import DocumentIngestionResponse
from src.application.services import DocumentIndexer
from src.application.use_cases import (
    DocumentTooLargeError,
    IngestDocumentInput,
    IngestDocumentUseCase,
)
from src.domain import (
    AssistantId,
    AssistantRepository,
    DocumentFileStorage,
    DocumentRepository,
    DomainValidationError,
    IndexOutdatedError,
    ReindexInProgressError,
    ReindexJobRepository,
    VectorStoreGateway,
)

router = APIRouter(
    prefix="/assistants/{assistant_id}/documents",
    tags=["documents"],
)


logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=DocumentIngestionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_document(
    assistant_id: str,
    file: UploadFile = File(...),
    metadata: str | None = Form(default=None),
    assistant_repository: AssistantRepository = Depends(get_assistant_repository),
    document_repository: DocumentRepository = Depends(get_document_repository),
    vector_store_gateway: VectorStoreGateway = Depends(get_vector_store_gateway),
    document_indexer: DocumentIndexer = Depends(get_document_indexer),
    file_storage: DocumentFileStorage = Depends(get_file_storage),
    reindex_job_repository: ReindexJobRepository = Depends(
        get_reindex_job_repository
    ),
    max_file_bytes: int = Depends(get_max_file_bytes),
) -> DocumentIngestionResponse:
    logger.info(
        "document.upload.started",
        extra={
            "assistant_id": assistant_id,
            "content_type": file.content_type,
            "has_metadata": metadata is not None,
        },
    )
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

    file_bytes = await file.read()
    logger.info(
        "document.upload.read",
        extra={"file_size_bytes": len(file_bytes)},
    )
    use_case = IngestDocumentUseCase(
        document_repository=document_repository,
        vector_store_gateway=vector_store_gateway,
        document_indexer=document_indexer,
        file_storage=file_storage,
        reindex_job_repository=reindex_job_repository,
        max_file_bytes=max_file_bytes,
    )
    try:
        # A vetorizacao em CPU e demorada: fora do laco de eventos, a API
        # continua respondendo (inclusive ao healthcheck) durante o upload.
        result = await run_in_threadpool(
            use_case.execute,
            IngestDocumentInput(
                assistant_id=assistant_ref.value,
                source_name=file.filename or "uploaded-document.txt",
                raw_content=file_bytes,
                content_type=file.content_type,
                metadata=_parse_metadata_field(metadata),
            ),
        )
    except DocumentTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except (IndexOutdatedError, ReindexInProgressError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (DomainValidationError, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return DocumentIngestionResponse(
        id=result.id,
        assistant_id=result.assistant_id,
        source_name=result.source_name,
        content_hash=result.content_hash,
        created_at=result.created_at,
        collection_name=result.collection_name,
        chunk_count=result.chunk_count,
        embedding_dimension=result.embedding_dimension,
        embedding_model=result.embedding_model,
        pipeline_version=result.pipeline_version,
    )


def _parse_metadata_field(raw_metadata: str | None) -> dict[str, str]:
    if raw_metadata is None or not raw_metadata.strip():
        return {}
    try:
        parsed = json.loads(raw_metadata)
    except JSONDecodeError as exc:
        raise ValueError(
            "metadata field must be a valid JSON object."
        ) from exc
    if not isinstance(parsed, dict):
        raise ValueError("metadata field must be a JSON object.")
    return {str(key): str(value) for key, value in parsed.items()}
