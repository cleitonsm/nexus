from __future__ import annotations

import os
from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from src.infrastructure.database import (
    PostgresAssistantRepository,
    PostgresConversationRepository,
    PostgresDocumentRepository,
    get_db_session,
)
from src.infrastructure.embeddings import LocalHashEmbeddingGateway
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


def get_embedding_gateway() -> LocalHashEmbeddingGateway:
    vector_size = int(os.getenv("EMBEDDING_VECTOR_SIZE", "384"))
    return LocalHashEmbeddingGateway(vector_size=vector_size)


def get_vector_store_gateway() -> QdrantVectorStoreGateway:
    qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
    return QdrantVectorStoreGateway(url=qdrant_url)
