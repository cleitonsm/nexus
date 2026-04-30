from __future__ import annotations

import os
from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from src.application.use_cases import GetGlobalApiKeyValueUseCase
from src.domain import ChatMessage, LLMGateway
from src.infrastructure.database import (
    PostgresAssistantRepository,
    PostgresConversationRepository,
    PostgresDocumentRepository,
    PostgresSecretSettingsRepository,
    get_db_session,
)
from src.infrastructure.embeddings import LocalHashEmbeddingGateway
from src.infrastructure.llm import HttpChatCompletionsLLM
from src.infrastructure.secrets import FernetSecretCipher
from src.infrastructure.vector_store import QdrantVectorStoreGateway


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


def get_embedding_gateway() -> LocalHashEmbeddingGateway:
    vector_size = int(os.getenv("EMBEDDING_VECTOR_SIZE", "384"))
    return LocalHashEmbeddingGateway(vector_size=vector_size)


def get_vector_store_gateway() -> QdrantVectorStoreGateway:
    qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
    return QdrantVectorStoreGateway(url=qdrant_url)


class UnconfiguredLLMGateway(LLMGateway):
    def generate(
        self,
        *,
        prompt: str,
        context_chunks: list[str],
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
    if not api_key:
        return UnconfiguredLLMGateway()
    api_url = os.getenv("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
    model = os.getenv("LLM_MODEL", "").strip()
    if not model:
        return UnconfiguredLLMGateway()
    return HttpChatCompletionsLLM(
        api_url=api_url,
        model=model,
        api_key=api_key,
    )
