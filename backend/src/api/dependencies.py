from __future__ import annotations

import logging
import os
from collections.abc import Generator, Iterator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from src.application.services import (
    AccessControl,
    AssistantRuntime,
    AssistantRuntimeResolver,
    AuditTrail,
    LLMGatewayBuilder,
    ResolvedLLM,
    build_assistant_runtime,
    ContextRetriever,
    DocumentIndexer,
    GroundedAnswerGenerator,
    RetrievalSettings,
    UsageGovernance,
    UsageSettings,
)
from src.application.use_cases import (
    GetGlobalApiKeyValueUseCase,
    resolve_llm_connection,
)
from src.domain import (
    Assistant,
    AuthenticatedUser,
    AuthenticationError,
    ChatMessage,
    ContextChunk,
    DocumentFileStorage,
    EmbeddingGateway,
    GroupDirectory,
    LLMCompletion,
    LLMConnection,
    LLMCredentialRepository,
    LLMGateway,
    LLMStreamChunk,
    MetricsRecorder,
    SecretCipher,
    SparseEncodingParameters,
    TokenCounter,
    TokenVerifier,
    Tracer,
)
from src.infrastructure.composition import (
    build_document_indexer,
    build_embedding_gateway,
    build_file_storage,
    build_group_directory,
    build_metrics,
    build_tracer,
    allow_insecure_llm_http,
    llm_connection_defaults,
    llm_timeout_seconds,
    usage_settings,
    build_reranker_gateway,
    build_sparse_embedding_gateway,
    build_token_counter,
    build_token_verifier,
    default_sparse_encoding_parameters,
    max_file_bytes,
    retrieval_settings,
    sparse_encoding_parameters,
)
from src.infrastructure.database import (
    PostgresAssistantPermissionRepository,
    PostgresAssistantRepository,
    PostgresAuditLogRepository,
    PostgresConversationRepository,
    PostgresDocumentRepository,
    PostgresFeedbackRepository,
    PostgresIndexParametersRepository,
    PostgresIngestionJobQueue,
    PostgresReindexJobRepository,
    PostgresSecretSettingsRepository,
    PostgresLLMConnectionRepository,
    PostgresUsageLimiter,
    PostgresUsageRecordRepository,
    PostgresUsageSettingsRepository,
    get_db_session,
)
from src.infrastructure.database.llm_credential_repository import (
    PostgresLLMCredentialRepository,
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


def build_index_parameters_repository(
    session: Session,
) -> PostgresIndexParametersRepository:
    """PC-D2: collections sem registro assumem os parametros padrao do BM25."""
    return PostgresIndexParametersRepository(
        session=session,
        assumed_when_missing=default_sparse_encoding_parameters(),
    )


def get_index_parameters_repository(
    session: Session = Depends(get_session),
) -> PostgresIndexParametersRepository:
    return build_index_parameters_repository(session)


def get_group_directory() -> GroupDirectory:
    return build_group_directory()


def get_sparse_encoding_parameters() -> SparseEncodingParameters:
    return sparse_encoding_parameters()


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
    MESSAGE = (
        "No LLM credential with an API key is configured. "
        "Register one in /admin/llm-credentials first."
    )

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


def get_llm_connection_repository(
    session: Session = Depends(get_session),
) -> PostgresLLMConnectionRepository:
    return PostgresLLMConnectionRepository(session=session)


def get_llm_connection_default() -> LLMConnection:
    return llm_connection_defaults()


def get_llm_insecure_http_allowed() -> bool:
    return allow_insecure_llm_http()


def get_effective_llm_connection(
    repository: PostgresLLMConnectionRepository = Depends(
        get_llm_connection_repository
    ),
) -> LLMConnection:
    """SPEC-008 RF-70: valor gravado pela tela, ou o do ambiente."""
    return resolve_llm_connection(repository, llm_connection_defaults())


def get_llm_gateway(
    secret_repository: PostgresSecretSettingsRepository = Depends(
        get_secret_settings_repository
    ),
    secret_cipher: FernetSecretCipher = Depends(get_secret_cipher),
    connection: LLMConnection = Depends(get_effective_llm_connection),
) -> LLMGateway:
    return build_llm_gateway(secret_repository, secret_cipher, connection)


def build_llm_gateway(
    secret_repository: PostgresSecretSettingsRepository,
    secret_cipher: FernetSecretCipher,
    connection: LLMConnection,
) -> LLMGateway:
    """A chave e decifrada so em memoria, a cada requisicao (ADR 0005)."""
    api_key = GetGlobalApiKeyValueUseCase(
        secret_repository=secret_repository,
        secret_cipher=secret_cipher,
    ).execute()
    logger.info(
        "llm.gateway.resolved",
        extra={
            "has_llm_credential": bool(api_key),
            "llm_provider": connection.provider.value,
            "llm_model": connection.model,
            "api_url_configured": bool(connection.api_url.strip()),
        },
    )
    if not api_key:
        return UnconfiguredLLMGateway()
    if not connection.model:
        return UnconfiguredLLMGateway()
    return TracedLLMGateway(
        HttpChatCompletionsLLM(
            api_url=connection.api_url,
            model=connection.model,
            api_key=api_key,
            timeout_seconds=llm_timeout_seconds(),
        ),
        build_tracer(),
        model=connection.model,
    )


def get_llm_credential_repository(
    session: Session = Depends(get_session),
) -> PostgresLLMCredentialRepository:
    return PostgresLLMCredentialRepository(session=session)


def build_llm_gateway_for(resolved: ResolvedLLM) -> LLMGateway:
    """SPEC-013: gateway da credencial resolvida; a chave so vive em memoria."""
    connection = resolved.connection
    logger.info(
        "llm.gateway.resolved",
        extra={
            "has_llm_credential": bool(resolved.api_key),
            "llm_source": resolved.source.value,
            "llm_credential_id": resolved.credential_id or "",
            "llm_provider": connection.provider.value,
            "llm_model": connection.model,
            "llm_model_fell_back": resolved.model_fell_back,
        },
    )
    if not resolved.api_key or not connection.model:
        return UnconfiguredLLMGateway()
    return TracedLLMGateway(
        HttpChatCompletionsLLM(
            api_url=connection.api_url,
            model=connection.model,
            api_key=resolved.api_key,
            timeout_seconds=llm_timeout_seconds(),
        ),
        build_tracer(),
        model=connection.model,
    )


def get_llm_gateway_builder() -> LLMGatewayBuilder:
    """Ponto de troca do LLM nos testes de integracao."""
    return build_llm_gateway_for


def build_assistant_runtime_resolver(
    *,
    base_settings: RetrievalSettings,
    credentials: LLMCredentialRepository,
    cipher: SecretCipher,
    gateway_builder: LLMGatewayBuilder,
) -> AssistantRuntimeResolver:
    """RN-40/RN-41 a cada pergunta, sobre o padrao do ambiente."""
    environment = llm_connection_defaults()
    currency = usage_settings().pricing.currency

    def resolve(assistant: Assistant) -> AssistantRuntime:
        return build_assistant_runtime(
            assistant,
            base_settings=base_settings,
            credentials=credentials,
            cipher=cipher,
            environment=environment,
            currency=currency,
            gateway_builder=gateway_builder,
        )

    return resolve


def get_assistant_runtime_resolver(
    context_retriever: ContextRetriever = Depends(get_context_retriever),
    credentials: PostgresLLMCredentialRepository = Depends(
        get_llm_credential_repository
    ),
    cipher: FernetSecretCipher = Depends(get_secret_cipher),
    gateway_builder: LLMGatewayBuilder = Depends(get_llm_gateway_builder),
) -> AssistantRuntimeResolver:
    return build_assistant_runtime_resolver(
        base_settings=context_retriever.settings,
        credentials=credentials,
        cipher=cipher,
        gateway_builder=gateway_builder,
    )


def get_usage_settings(
    connection: LLMConnection = Depends(get_effective_llm_connection),
) -> UsageSettings:
    return usage_settings(model=connection.model)


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
        settings=usage_settings(
            model=resolve_llm_connection(
                PostgresLLMConnectionRepository(session=session),
                llm_connection_defaults(),
            ).model
        ),
        metrics=build_metrics(),
    )


def get_usage_governance(
    session: Session = Depends(get_session),
) -> UsageGovernance:
    return build_usage_governance(session)


def get_answer_generator() -> GroundedAnswerGenerator:
    """Base do chat sem assistente resolvido; com assistente, vale o
    ``get_assistant_runtime_resolver`` (SPEC-013)."""
    return GroundedAnswerGenerator(llm_gateway=UnconfiguredLLMGateway())
