from __future__ import annotations

import json
import os
from collections.abc import Generator
from pathlib import Path
import time
from uuid import uuid4

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

DEFAULT_LLM_MODEL = "gpt-4o-mini"


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
    qdrant_api_key = os.getenv("QDRANT_API_KEY", "") or None
    return QdrantVectorStoreGateway(url=qdrant_url, api_key=qdrant_api_key)


def _agent_debug_log(
    *,
    run_id: str,
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict[str, object],
) -> None:
    payload = {
        "sessionId": "a1f259",
        "id": f"log_{int(time.time() * 1000)}_{uuid4().hex[:8]}",
        "timestamp": int(time.time() * 1000),
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
    }
    try:
        with Path("debug-a1f259.log").open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except OSError:
        pass


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
    api_url = os.getenv("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
    model = get_configured_llm_model()
    # region agent log
    _agent_debug_log(
        run_id="llm-ui-pre-fix",
        hypothesis_id="H7",
        location="backend/src/api/dependencies.py:get_llm_gateway",
        message="resolved llm gateway configuration",
        data={
            "hasApiKey": bool(api_key),
            "model": model,
            "apiUrlConfigured": bool(api_url.strip()),
        },
    )
    # endregion
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
