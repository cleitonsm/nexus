from __future__ import annotations

import logging
import os
from collections.abc import Callable, Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from src.application.services import (
    ContextRetriever,
    DocumentIndexer,
    GroundedAnswerGenerator,
)
from src.application.use_cases import (
    GetGlobalApiKeyValueUseCase,
    RunReindexInput,
    RunReindexUseCase,
)
from src.domain import (
    ChatMessage,
    ContextChunk,
    DocumentFileStorage,
    EmbeddingGateway,
    LLMGateway,
    TokenCounter,
)
from src.infrastructure.composition import (
    build_document_indexer,
    build_embedding_gateway,
    build_file_storage,
    build_reranker_gateway,
    build_sparse_embedding_gateway,
    build_token_counter,
    max_file_bytes,
    retrieval_settings,
)
from src.infrastructure.database import (
    PostgresAssistantRepository,
    PostgresConversationRepository,
    PostgresDocumentRepository,
    PostgresReindexJobRepository,
    PostgresSecretSettingsRepository,
    SessionLocal,
    get_db_session,
)
from src.infrastructure.llm import HttpChatCompletionsLLM
from src.infrastructure.secrets import FernetSecretCipher
from src.infrastructure.vector_store import QdrantVectorStoreGateway

DEFAULT_LLM_MODEL = "gpt-4o-mini"

logger = logging.getLogger(__name__)


def get_session() -> Generator[Session, None, None]:
    yield from get_db_session()


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
    return ContextRetriever(
        embedding_gateway=embedding_gateway,
        sparse_embedding_gateway=build_sparse_embedding_gateway(),
        vector_store_gateway=vector_store_gateway,
        reranker_gateway=build_reranker_gateway(),
        settings=retrieval_settings(),
    )


class UnconfiguredLLMGateway(LLMGateway):
    def generate(
        self,
        *,
        prompt: str,
        context_chunks: list[ContextChunk],
        conversation_history: list[ChatMessage],
    ) -> str:
        raise ValueError(
            "Global LLM API key is not configured. Set it in /admin/api-key first."
        )


def get_llm_gateway(
    secret_repository: PostgresSecretSettingsRepository = Depends(
        get_secret_settings_repository
    ),
    secret_cipher: FernetSecretCipher = Depends(get_secret_cipher),
) -> LLMGateway:
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
    return HttpChatCompletionsLLM(
        api_url=api_url,
        model=model,
        api_key=api_key,
    )


def get_configured_llm_model() -> str:
    model = os.getenv("LLM_MODEL", "").strip()
    if not model or model == "placeholder":
        return DEFAULT_LLM_MODEL
    return model


def get_answer_generator(
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
) -> GroundedAnswerGenerator:
    return GroundedAnswerGenerator(llm_gateway=llm_gateway)
