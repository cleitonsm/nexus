from __future__ import annotations

import json
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

from src.api.dependencies import (
    get_assistant_repository,
    get_document_repository,
    get_embedding_gateway,
    get_vector_store_gateway,
)
from src.api.schemas import DocumentIngestionResponse
from src.application.use_cases import (
    IngestDocumentInput,
    IngestDocumentUseCase,
)
from src.domain import AssistantId, DomainValidationError
from src.infrastructure.database import (
    PostgresAssistantRepository,
    PostgresDocumentRepository,
)
from src.infrastructure.documents import extract_supported_text
from src.infrastructure.embeddings import LocalHashEmbeddingGateway
from src.infrastructure.vector_store import QdrantVectorStoreGateway

router = APIRouter(
    prefix="/assistants/{assistant_id}/documents",
    tags=["documents"],
)


@router.post(
    "",
    response_model=DocumentIngestionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_document(
    assistant_id: str,
    file: UploadFile = File(...),
    metadata: str | None = Form(default=None),
    assistant_repository: PostgresAssistantRepository = Depends(
        get_assistant_repository
    ),
    document_repository: PostgresDocumentRepository = Depends(
        get_document_repository
    ),
    embedding_gateway: LocalHashEmbeddingGateway = Depends(
        get_embedding_gateway
    ),
    vector_store_gateway: QdrantVectorStoreGateway = Depends(
        get_vector_store_gateway
    ),
) -> DocumentIngestionResponse:
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
    try:
        extracted_text = extract_supported_text(
            filename=file.filename,
            content_type=file.content_type,
            raw_content=file_bytes,
        )
        parsed_metadata = _parse_metadata_field(metadata)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    use_case = IngestDocumentUseCase(
        document_repository=document_repository,
        embedding_gateway=embedding_gateway,
        vector_store_gateway=vector_store_gateway,
    )
    try:
        result = use_case.execute(
            IngestDocumentInput(
                assistant_id=assistant_ref.value,
                source_name=file.filename or "uploaded-document.txt",
                content=extracted_text,
                metadata=parsed_metadata,
            )
        )
    except (DomainValidationError, ValueError) as exc:
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
