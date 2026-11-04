"""SPEC-018: rotas do resumidor de documentos (RF-114 a RF-119).

Conversa de outra pessoa responde 404, nunca 403, para nao revelar que ela
existe (RN-24, RN-58). Os 409 e o 429 do resumidor saem pelos tratadores
globais com ``code`` estavel (``api/errors.py``).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from src.api.dependencies import (
    get_access_control,
    get_conversation_repository,
    get_current_user,
    get_document_indexer,
    get_document_repository,
    get_document_summary_repository,
    get_file_storage,
    get_ingestion_job_queue,
    get_max_file_bytes,
)
from src.api.schemas import (
    CitationResponse,
    StoredSummaryResponse,
    SummarizerInfoResponse,
    SummaryDocumentResponse,
)
from src.api.uploads import parse_content_length, read_upload_limited
from src.application.dto import StoredSummaryDTO, SummaryDocumentDTO
from src.application.services import AccessControl, DocumentIndexer
from src.application.use_cases import ConversationNotFoundError, DocumentTooLargeError
from src.application.use_cases.summary_documents import (
    GetStoredSummaryUseCase,
    GetSummarizerInfoUseCase,
    GetSummaryDocumentStatusUseCase,
    RetrySummaryUseCase,
    SummaryConversationInput,
    SummaryDocumentNotFoundError,
    UnsupportedDocumentFormatError,
    UploadSummaryDocumentInput,
    UploadSummaryDocumentUseCase,
)
from src.domain import (
    AuthenticatedUser,
    ConversationRepository,
    DocumentFileStorage,
    DocumentRepository,
    DocumentSummaryRepository,
    DomainValidationError,
    IngestionJobQueue,
)

router = APIRouter(tags=["summarizer"], dependencies=[Depends(get_current_user)])


@contextmanager
def _translate_errors() -> Iterator[None]:
    try:
        yield
    except ConversationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="conversation not found") from exc
    except SummaryDocumentNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "summary_document_not_found", "message": str(exc)},
        ) from exc
    except DocumentTooLargeError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except UnsupportedDocumentFormatError as exc:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"code": "unsupported_format", "message": str(exc)},
        ) from exc
    except (DomainValidationError, ValueError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/summarizer", response_model=SummarizerInfoResponse)
def get_summarizer(
    user: AuthenticatedUser = Depends(get_current_user),
    max_bytes: int = Depends(get_max_file_bytes),
) -> SummarizerInfoResponse:
    """RF-119: finalidade e especificacoes, montadas das constantes (D37)."""
    info = GetSummarizerInfoUseCase(max_file_bytes=max_bytes).execute(user)
    return SummarizerInfoResponse(
        assistant_id=info.assistant_id,
        formats=list(info.formats),
        max_bytes=info.max_bytes,
        max_megabytes_label=info.max_megabytes_label,
        max_tokens=info.max_tokens,
        pages_hint=info.pages_hint,
        retention_days=info.retention_days,
        daily_limit=info.daily_limit,
        out_of_scope=list(info.out_of_scope),
        welcome_markdown=info.welcome_markdown,
    )


@router.post(
    "/conversations/{conversation_id}/document",
    response_model=SummaryDocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    conversation_id: str,
    request: Request,
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user),
    access_control: AccessControl = Depends(get_access_control),
    conversations: ConversationRepository = Depends(get_conversation_repository),
    documents: DocumentRepository = Depends(get_document_repository),
    summaries: DocumentSummaryRepository = Depends(get_document_summary_repository),
    document_indexer: DocumentIndexer = Depends(get_document_indexer),
    file_storage: DocumentFileStorage = Depends(get_file_storage),
    job_queue: IngestionJobQueue = Depends(get_ingestion_job_queue),
    max_file_bytes: int = Depends(get_max_file_bytes),
) -> SummaryDocumentResponse:
    """RF-114 e RNF-39: guarda e enfileira; o worker extrai, indexa e resume."""
    with _translate_errors():
        raw = await read_upload_limited(
            file,
            max_file_bytes,
            content_length=parse_content_length(request.headers.get("content-length")),
        )
    use_case = UploadSummaryDocumentUseCase(
        conversations=conversations,
        documents=documents,
        summaries=summaries,
        document_indexer=document_indexer,
        file_storage=file_storage,
        job_queue=job_queue,
        access_control=access_control,
        max_file_bytes=max_file_bytes,
    )
    with _translate_errors():
        result = await run_in_threadpool(
            use_case.execute,
            UploadSummaryDocumentInput(
                user=user,
                conversation_id=conversation_id,
                source_name=file.filename or "documento.txt",
                raw_content=raw,
                content_type=file.content_type,
            ),
        )
    return _document_response(result)


def _reader(cls):
    def build(
        access_control: AccessControl = Depends(get_access_control),
        conversations: ConversationRepository = Depends(get_conversation_repository),
        documents: DocumentRepository = Depends(get_document_repository),
        summaries: DocumentSummaryRepository = Depends(get_document_summary_repository),
        job_queue: IngestionJobQueue = Depends(get_ingestion_job_queue),
    ):
        kwargs = {
            "conversations": conversations,
            "documents": documents,
            "summaries": summaries,
            "access_control": access_control,
        }
        if cls is RetrySummaryUseCase:
            kwargs["job_queue"] = job_queue
        return cls(**kwargs)

    return build


@router.get(
    "/conversations/{conversation_id}/document",
    response_model=SummaryDocumentResponse,
)
def get_document_status(
    conversation_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    use_case: GetSummaryDocumentStatusUseCase = Depends(_reader(GetSummaryDocumentStatusUseCase)),
) -> SummaryDocumentResponse:
    """RF-115 e D36: etapa e andamento, consultados a cada 3 s pela tela."""
    with _translate_errors():
        result = use_case.execute(SummaryConversationInput(user=user, conversation_id=conversation_id))
    return _document_response(result)


@router.get(
    "/conversations/{conversation_id}/summary",
    response_model=StoredSummaryResponse,
)
def get_summary(
    conversation_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    use_case: GetStoredSummaryUseCase = Depends(_reader(GetStoredSummaryUseCase)),
) -> StoredSummaryResponse:
    """RF-117 e RNF-37: o resumo gravado, sem chamar o LLM."""
    with _translate_errors():
        result = use_case.execute(SummaryConversationInput(user=user, conversation_id=conversation_id))
    return _summary_response(result)


@router.post(
    "/conversations/{conversation_id}/summary/retry",
    response_model=SummaryDocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_summary(
    conversation_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    use_case: RetrySummaryUseCase = Depends(_reader(RetrySummaryUseCase)),
) -> SummaryDocumentResponse:
    """RN-64: refaz so o resumo, sem nova cota."""
    with _translate_errors():
        result = use_case.execute(SummaryConversationInput(user=user, conversation_id=conversation_id))
    return _document_response(result)


def _document_response(item: SummaryDocumentDTO) -> SummaryDocumentResponse:
    return SummaryDocumentResponse(
        document_id=item.document_id,
        conversation_id=item.conversation_id,
        source_name=item.source_name,
        size_bytes=item.size_bytes,
        stage=item.stage,
        done=item.done,
        total=item.total,
        failure_code=item.failure_code,
        failure_detail=item.failure_detail,
        questions_available=item.questions_available,
        created_at=item.created_at,
        expires_at=item.expires_at,
    )


def _summary_response(item: StoredSummaryDTO) -> StoredSummaryResponse:
    return StoredSummaryResponse(
        document_id=item.document_id,
        content=item.content,
        citations=[
            CitationResponse(
                number=citation.number,
                document_id=citation.document_id,
                chunk_id=citation.chunk_id,
                source_name=citation.source_name,
                section_path=citation.section_path,
                page=citation.page,
                score=citation.score,
                excerpt=citation.excerpt,
                document_available=citation.document_available,
            )
            for citation in item.citations
        ],
        prompt_version=item.prompt_version,
        model=item.model,
        updated_at=item.updated_at,
    )
