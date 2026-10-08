from __future__ import annotations

import logging
import os
from collections.abc import Callable, Generator, Iterator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from src.application.services import (
    AccessControl,
    AuditTrail,
    ContextRetriever,
    DocumentIndexer,
    GroundedAnswerGenerator,
    UsageGovernance,
    UsageSettings,
)
from src.application.use_cases import (
    GetGlobalApiKeyValueUseCase,
    RunReindexInput,
    RunReindexUseCase,
)
from src.domain import (
    AuthenticatedUser,
    AuthenticationError,
    ChatMessage,
    ContextChunk,
    DocumentFileStorage,
    EmbeddingGateway,
    LLMCompletion,
    LLMGateway,
    LLMStreamChunk,
    MetricsRecorder,
    TokenCounter,
    TokenVerifier,
    Tracer,
)
from src.infrastructure.composition import (
    build_document_indexer,
    build_embedding_gateway,
    build_file_storage,
    build_metrics,
    build_tracer,
    llm_model_name,
    usage_settings,
    build_reranker_gateway,
    build_sparse_embedding_gateway,
    build_token_counter,
    build_token_verifier,
    max_file_bytes,
    retrieval_settings,
)
from src.infrastructure.database import (
    PostgresAssistantPermissionRepository,
    PostgresAssistantRepository,
    PostgresAuditLogRepository,
    PostgresConversationRepository,
    PostgresDocumentRepository,
    PostgresFeedbackRepository,
    PostgresIngestionJobQueue,
    PostgresReindexJobRepository,
    PostgresSecretSettingsRepository,
    PostgresUsageLimiter,
    PostgresUsageRecordRepository,
    PostgresUsageSettingsRepository,
    SessionLocal,
    get_db_session,
)
from src.infrastructure.llm import HttpChatCompletionsLLM
from src.infrastructure.observability import (
    TracedLLMGateway,
    TracedTokenVerifier,
    TracedVectorStore,
)
from src.infrastructure.secrets import FernetSecretCipher
from src.infrastructure.vector_store import QdrantVectorStoreGateway

logger = logging.getLogger(__name__)


def get_session() -> Generator[Session, None, None]:
    yield from get_db_session()


def get_tracer() -> Tracer:
    return build_tracer()


def get_metrics() -> MetricsRecorder:
    return build_metrics()


def get_token_verifier() -> TokenVerifier:
    return TracedTokenVerifier(build_token_verifier(), build_tracer())


def get_current_user(
    authorization: str | None = Header(default=None),
    token_verifier: TokenVerifier = Depends(get_token_verifier),
) -> AuthenticatedUser:
    """RF-40: toda rota, exceto ``/health``, exige um token valido.

    O token nunca e registrado em log (RNF-25); so o motivo da recusa.
    """
    scheme, _, token = (authorization or "").strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _unauthenticated("authentication required")
    try:
        return token_verifier.verify(token.strip())
    except AuthenticationError as exc:
        logger.info("auth.token.rejected", extra={"reason": str(exc)})
        raise _unauthenticated("invalid or expired token") from exc


def _unauthenticated(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_permission_repository(
    session: Session = Depends(get_session),
) -> PostgresAssistantPermissionRepository:
    return PostgresAssistantPermissionRepository(session=session)


def get_audit_log_repository(
    session: Session = Depends(get_session),
) -> PostgresAuditLogRepository:
    return PostgresAuditLogRepository(session=session)


def get_access_control(
    permission_repository: PostgresAssistantPermissionRepository = Depends(
        get_permission_repository
    ),
    audit_log_repository: PostgresAuditLogRepository = Depends(
        get_audit_log_repository
    ),
) -> AccessControl:
    return AccessControl(
        permission_repository=permission_repository,
        audit_trail=AuditTrail(audit_log_repository),
    )


def get_assistant_repository(
    session: Session = Depends(get_session),
) -> PostgresAssistantRepository:
    return PostgresAssistantRepository(session=session)


def get_conversation_repository(
    session: Session = Depends(get_session),
) -> PostgresConversationRepository:
    return PostgresConversationRepository(session=session)


def get_document_repository(
    session: Session = Depends(get_session),
) -> PostgresDocumentRepository:
    return PostgresDocumentRepository(session=session)


def get_secret_settings_repository(
    session: Session = Depends(get_session),
) -> PostgresSecretSettingsRepository:
    return PostgresSecretSettingsRepository(session=session)


def get_secret_cipher() -> FernetSecretCipher:
    master_key = os.getenv("NEXUS_SECRETS_KEY", "")
    return FernetSecretCipher(master_key=master_key)


def get_reindex_job_repository(
    session: Session = Depends(get_session),
) -> PostgresReindexJobRepository:
    return PostgresReindexJobRepository(session=session)


def get_ingestion_job_queue(
    session: Session = Depends(get_session),
) -> PostgresIngestionJobQueue:
    return PostgresIngestionJobQueue(session=session)


def get_embedding_gateway() -> EmbeddingGateway:
    """O modelo e carregado uma unica vez por processo."""
    return build_embedding_gateway()


def get_document_indexer() -> DocumentIndexer:
    return build_document_indexer()


def get_file_storage() -> DocumentFileStorage:
    return build_file_storage()


def get_max_file_bytes() -> int:
    return max_file_bytes()


def run_reindex_job(job_id: str) -> None:
    """Executa a reindexacao em segundo plano, com sessao de banco propria."""
    with SessionLocal() as session:
        RunReindexUseCase(
            document_repository=PostgresDocumentRepository(session=session),
            vector_store_gateway=get_vector_store_gateway(),
            document_indexer=build_document_indexer(),
            file_storage=build_file_storage(),
            reindex_job_repository=PostgresReindexJobRepository(session=session),
            permission_repository=PostgresAssistantPermissionRepository(
                session=session
            ),
        ).execute(RunReindexInput(job_id=job_id))


def get_reindex_runner() -> Callable[[str], None]:
    return run_reindex_job


def get_vector_store_gateway() -> QdrantVectorStoreGateway:
    qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY", "") or None
    return QdrantVectorStoreGateway(url=qdrant_url, api_key=qdrant_api_key)


def get_token_counter() -> TokenCounter:
    return build_token_counter()


def get_context_retriever(
    embedding_gateway: EmbeddingGateway = Depends(get_embedding_gateway),
    vector_store_gateway: QdrantVectorStoreGateway = Depends(
        get_vector_store_gateway
    ),
) -> ContextRetriever:
    """Os modelos locais sao carregados uma unica vez por processo."""
    return build_context_retriever(embedding_gateway, vector_store_gateway)


def build_context_retriever(
    embedding_gateway: EmbeddingGateway,
    vector_store_gateway: QdrantVectorStoreGateway,
) -> ContextRetriever:
    return ContextRetriever(
        embedding_gateway=embedding_gateway,
        sparse_embedding_gateway=build_sparse_embedding_gateway(),
        vector_store_gateway=TracedVectorStore(vector_store_gateway, build_tracer()),
        reranker_gateway=build_reranker_gateway(),
        settings=retrieval_settings(),
    )


class UnconfiguredLLMGateway(LLMGateway):
    MESSAGE = "Global LLM API key is not configured. Set it in /admin/api-key first."

    def generate(
        self,
        *,
        prompt: str,
        context_chunks: list[ContextChunk],
        conversation_history: list[ChatMessage],
    ) -> str:
        raise ValueError(self.MESSAGE)

    def generate_with_usage(self, **kwargs: object) -> LLMCompletion:
        raise ValueError(self.MESSAGE)

    def generate_stream(self, **kwargs: object) -> Iterator[LLMStreamChunk]:
        raise ValueError(self.MESSAGE)


def get_llm_gateway(
    secret_repository: PostgresSecretSettingsRepository = Depends(
        get_secret_settings_repository
    ),
    secret_cipher: FernetSecretCipher = Depends(get_secret_cipher),
) -> LLMGateway:
    return build_llm_gateway(secret_repository, secret_cipher)


def build_llm_gateway(
    secret_repository: PostgresSecretSettingsRepository,
    secret_cipher: FernetSecretCipher,
) -> LLMGateway:
    """A chave e decifrada so em memoria, a cada requisicao (ADR 0005)."""
    api_key = GetGlobalApiKeyValueUseCase(
        secret_repository=secret_repository,
        secret_cipher=secret_cipher,
    ).execute()
    api_url = os.getenv("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
    model = get_configured_llm_model()
    logger.info(
        "llm.gateway.resolved",
        extra={
            "has_llm_credential": bool(api_key),
            "llm_model": model,
            "api_url_configured": bool(api_url.strip()),
        },
    )
    if not api_key:
        return UnconfiguredLLMGateway()
    if not model:
        return UnconfiguredLLMGateway()
    return TracedLLMGateway(
        HttpChatCompletionsLLM(
            api_url=api_url,
            model=model,
            api_key=api_key,
        ),
        build_tracer(),
        model=model,
    )


def get_configured_llm_model() -> str:
    return llm_model_name()


def get_usage_settings() -> UsageSettings:
    return usage_settings()


def get_usage_record_repository(
    session: Session = Depends(get_session),
) -> PostgresUsageRecordRepository:
    return PostgresUsageRecordRepository(session=session)


def get_usage_settings_repository(
    session: Session = Depends(get_session),
) -> PostgresUsageSettingsRepository:
    return PostgresUsageSettingsRepository(session=session)


def get_feedback_repository(
    session: Session = Depends(get_session),
) -> PostgresFeedbackRepository:
    return PostgresFeedbackRepository(session=session)


def build_usage_governance(session: Session) -> UsageGovernance:
    return UsageGovernance(
        limiter=PostgresUsageLimiter(session=session),
        record_repository=PostgresUsageRecordRepository(session=session),
        settings_repository=PostgresUsageSettingsRepository(session=session),
        settings=usage_settings(),
        metrics=build_metrics(),
    )


def get_usage_governance(
    session: Session = Depends(get_session),
) -> UsageGovernance:
    return build_usage_governance(session)


def get_answer_generator(
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
) -> GroundedAnswerGenerator:
    return GroundedAnswerGenerator(llm_gateway=llm_gateway)
