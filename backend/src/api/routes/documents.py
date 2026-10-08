from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from json import JSONDecodeError

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool

from src.api.dependencies import (
    get_access_control,
    get_assistant_repository,
    get_current_user,
    get_document_indexer,
    get_document_repository,
    get_file_storage,
    get_ingestion_job_queue,
    get_max_file_bytes,
    get_reindex_job_repository,
    get_vector_store_gateway,
)
from src.api.schemas import DocumentAccessResponse, GroupsRequest
from src.application.dto import DocumentAccessDTO
from src.application.services import AccessControl, DocumentIndexer
from src.application.use_cases import (
    DeleteDocumentUseCase,
    DocumentNotFoundError,
    DocumentRefInput,
    DocumentTooLargeError,
    GetDocumentUseCase,
    IngestDocumentInput,
    IngestDocumentUseCase,
    ListDocumentsInput,
    ListDocumentsUseCase,
    ReplaceDocumentInput,
    ReplaceDocumentUseCase,
    ReprocessDocumentInput,
    ReprocessDocumentUseCase,
    SetDocumentGroupsInput,
    SetDocumentGroupsUseCase,
)
from src.domain import (
    AssistantId,
    AssistantRepository,
    AuthenticatedUser,
    DocumentFileStorage,
    DocumentRepository,
    DomainValidationError,
    DuplicateDocumentError,
    IndexOutdatedError,
    IngestionJobQueue,
    InvalidDocumentStateError,
    ReindexInProgressError,
    ReindexJobRepository,
    VectorStoreGateway,
)

router = APIRouter(
    prefix="/assistants/{assistant_id}/documents",
    tags=["documents"],
    dependencies=[Depends(get_current_user)],
)
# Operacoes sobre um documento: o assistente vem do proprio registro.
document_router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    dependencies=[Depends(get_current_user)],
)


logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=DocumentAccessResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_document(
    assistant_id: str,
    file: UploadFile = File(...),
    metadata: str | None = Form(default=None),
    groups: str | None = Form(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    assistant_repository: AssistantRepository = Depends(get_assistant_repository),
    document_repository: DocumentRepository = Depends(get_document_repository),
    vector_store_gateway: VectorStoreGateway = Depends(get_vector_store_gateway),
    document_indexer: DocumentIndexer = Depends(get_document_indexer),
    file_storage: DocumentFileStorage = Depends(get_file_storage),
    job_queue: IngestionJobQueue = Depends(get_ingestion_job_queue),
    max_file_bytes: int = Depends(get_max_file_bytes),
) -> DocumentAccessResponse:
    """RF-48: guarda o original e enfileira; o worker indexa em segundo plano.

    Responde 202 com o documento pendente; 409 para arquivo ja enviado ao
    assistente (RN-26), com o documento existente no corpo.
    """
    assistant_ref = _assistant_ref(assistant_id)
    if assistant_repository.get_by_id(assistant_ref) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="assistant not found",
        )
    file_bytes = await file.read()
    logger.info(
        "document.upload.received",
        extra={
            "assistant_id": assistant_ref.value,
            "content_type": file.content_type,
            "file_size_bytes": len(file_bytes),
        },
    )
    use_case = IngestDocumentUseCase(
        document_repository=document_repository,
        vector_store_gateway=vector_store_gateway,
        document_indexer=document_indexer,
        file_storage=file_storage,
        job_queue=job_queue,
        max_file_bytes=max_file_bytes,
        access_control=access_control,
    )
    with _translate_errors():
        result = await run_in_threadpool(
            use_case.execute,
            IngestDocumentInput(
                user=user,
                assistant_id=assistant_ref.value,
                source_name=file.filename or "uploaded-document.txt",
                raw_content=file_bytes,
                content_type=file.content_type,
                metadata=_parse_metadata_field(metadata),
                groups=_parse_groups_field(groups),
            ),
        )
    return _document_response(result)


@router.get("", response_model=list[DocumentAccessResponse])
def list_documents(
    assistant_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    assistant_repository: AssistantRepository = Depends(get_assistant_repository),
    document_repository: DocumentRepository = Depends(get_document_repository),
) -> list[DocumentAccessResponse]:
    """Documentos vigentes do assistente, com estado e restricao (RF-49, HU-25)."""
    assistant_ref = _assistant_ref(assistant_id)
    if assistant_repository.get_by_id(assistant_ref) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="assistant not found",
        )
    documents = ListDocumentsUseCase(
        document_repository=document_repository,
        access_control=access_control,
    ).execute(ListDocumentsInput(user=user, assistant_id=assistant_ref.value))
    return [_document_response(item) for item in documents]


@document_router.get("/{document_id}", response_model=DocumentAccessResponse)
def get_document(
    document_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    document_repository: DocumentRepository = Depends(get_document_repository),
) -> DocumentAccessResponse:
    """RF-49: estado atual, consultado pela tela enquanto o documento processa."""
    with _translate_errors():
        result = GetDocumentUseCase(
            document_repository=document_repository,
            access_control=access_control,
        ).execute(DocumentRefInput(user=user, document_id=document_id))
    return _document_response(result)


@document_router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    document_repository: DocumentRepository = Depends(get_document_repository),
    vector_store_gateway: VectorStoreGateway = Depends(get_vector_store_gateway),
    file_storage: DocumentFileStorage = Depends(get_file_storage),
    reindex_job_repository: ReindexJobRepository = Depends(
        get_reindex_job_repository
    ),
) -> Response:
    """RF-50, RN-29: remove trechos, arquivo original e registro."""
    with _translate_errors():
        DeleteDocumentUseCase(
            document_repository=document_repository,
            vector_store_gateway=vector_store_gateway,
            file_storage=file_storage,
            reindex_job_repository=reindex_job_repository,
            access_control=access_control,
        ).execute(DocumentRefInput(user=user, document_id=document_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@document_router.put(
    "/{document_id}/content",
    response_model=DocumentAccessResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def replace_document(
    document_id: str,
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    document_repository: DocumentRepository = Depends(get_document_repository),
    vector_store_gateway: VectorStoreGateway = Depends(get_vector_store_gateway),
    document_indexer: DocumentIndexer = Depends(get_document_indexer),
    file_storage: DocumentFileStorage = Depends(get_file_storage),
    job_queue: IngestionJobQueue = Depends(get_ingestion_job_queue),
    max_file_bytes: int = Depends(get_max_file_bytes),
) -> DocumentAccessResponse:
    """RF-51, RN-28: a nova versao fica pendente; a atual responde ate o fim."""
    file_bytes = await file.read()
    use_case = ReplaceDocumentUseCase(
        document_repository=document_repository,
        vector_store_gateway=vector_store_gateway,
        document_indexer=document_indexer,
        file_storage=file_storage,
        job_queue=job_queue,
        max_file_bytes=max_file_bytes,
        access_control=access_control,
    )
    with _translate_errors():
        result = await run_in_threadpool(
            use_case.execute,
            ReplaceDocumentInput(
                user=user,
                document_id=document_id,
                source_name=file.filename or "uploaded-document.txt",
                raw_content=file_bytes,
                content_type=file.content_type,
            ),
        )
    return _document_response(result)


@document_router.post(
    "/{document_id}/reprocess",
    response_model=DocumentAccessResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def reprocess_document(
    document_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    document_repository: DocumentRepository = Depends(get_document_repository),
    job_queue: IngestionJobQueue = Depends(get_ingestion_job_queue),
) -> DocumentAccessResponse:
    """RF-54: documento que falhou volta a fila, a partir do original guardado."""
    with _translate_errors():
        result = ReprocessDocumentUseCase(
            document_repository=document_repository,
            job_queue=job_queue,
            access_control=access_control,
        ).execute(ReprocessDocumentInput(user=user, document_id=document_id))
    return _document_response(result)


@document_router.put("/{document_id}/groups", response_model=DocumentAccessResponse)
def set_document_groups(
    document_id: str,
    payload: GroupsRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    document_repository: DocumentRepository = Depends(get_document_repository),
    vector_store_gateway: VectorStoreGateway = Depends(get_vector_store_gateway),
    reindex_job_repository: ReindexJobRepository = Depends(
        get_reindex_job_repository
    ),
) -> DocumentAccessResponse:
    """RF-43: restringe o documento a grupos; lista vazia remove a restricao."""
    use_case = SetDocumentGroupsUseCase(
        document_repository=document_repository,
        vector_store_gateway=vector_store_gateway,
        reindex_job_repository=reindex_job_repository,
        access_control=access_control,
    )
    with _translate_errors():
        result = use_case.execute(
            SetDocumentGroupsInput(
                user=user,
                document_id=document_id,
                groups=tuple(payload.groups),
            )
        )
    return _document_response(result)


@contextmanager
def _translate_errors() -> Iterator[None]:
    """Traduz os erros dos casos de uso de documentos para HTTP."""
    try:
        yield
    except DuplicateDocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "duplicate_document",
                "message": str(exc),
                "document_id": exc.existing_document_id,
                "source_name": exc.existing_source_name,
            },
        ) from exc
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        ) from exc
    except DocumentTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except (
        IndexOutdatedError,
        ReindexInProgressError,
        InvalidDocumentStateError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (DomainValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


def _assistant_ref(assistant_id: str) -> AssistantId:
    try:
        return AssistantId(assistant_id)
    except DomainValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


def _document_response(item: DocumentAccessDTO) -> DocumentAccessResponse:
    return DocumentAccessResponse(
        id=item.id,
        assistant_id=item.assistant_id,
        source_name=item.source_name,
        created_at=item.created_at,
        chunk_count=item.chunk_count,
        groups=list(item.groups),
        status=item.status,
        version=item.version,
        failure_reason=item.failure_reason,
        size_bytes=item.size_bytes,
        replaces_document_id=item.replaces_document_id,
        content_hash=item.content_hash,
        has_original=item.has_original,
    )


def _parse_groups_field(raw_groups: str | None) -> tuple[str, ...]:
    """Campo ``groups`` do formulario: lista JSON de nomes, como ``metadata``."""
    if raw_groups is None or not raw_groups.strip():
        return ()
    try:
        parsed = json.loads(raw_groups)
    except JSONDecodeError as exc:
        raise _invalid_form("groups field must be a JSON array of strings.") from exc
    if not isinstance(parsed, list) or not all(
        isinstance(item, str) for item in parsed
    ):
        raise _invalid_form("groups field must be a JSON array of strings.")
    return tuple(parsed)


def _parse_metadata_field(raw_metadata: str | None) -> dict[str, str]:
    if raw_metadata is None or not raw_metadata.strip():
        return {}
    try:
        parsed = json.loads(raw_metadata)
    except JSONDecodeError as exc:
        raise _invalid_form("metadata field must be a valid JSON object.") from exc
    if not isinstance(parsed, dict):
        raise _invalid_form("metadata field must be a JSON object.")
    return {str(key): str(value) for key, value in parsed.items()}


def _invalid_form(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=detail,
    )
