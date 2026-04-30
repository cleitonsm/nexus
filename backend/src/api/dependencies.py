from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from src.infrastructure.database import (
    PostgresAssistantRepository,
    PostgresConversationRepository,
    get_db_session,
)


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
