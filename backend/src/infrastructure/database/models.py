from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AssistantModel(Base):
    __tablename__ = "assistants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    initial_prompt: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )

    conversations: Mapped[list[ConversationModel]] = relationship(
        back_populates="assistant",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list[DocumentModel]] = relationship(
        back_populates="assistant",
        cascade="all, delete-orphan",
    )


class DocumentModel(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assistant_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("assistants.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[str] = mapped_column(
        Text(),
        default="{}",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )

    embedding_model: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    pipeline_version: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer(),
        default=0,
        server_default="0",
        nullable=False,
    )
    storage_key: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    assistant: Mapped[AssistantModel] = relationship(
        back_populates="documents"
    )


class ConversationModel(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assistant_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("assistants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )

    assistant: Mapped[AssistantModel] = relationship(
        back_populates="conversations"
    )
    messages: Mapped[list[MessageModel]] = relationship(
        back_populates="conversation",
        order_by="MessageModel.created_at",
        cascade="all, delete-orphan",
    )


class MessageModel(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )

    conversation: Mapped[ConversationModel] = relationship(
        back_populates="messages"
    )


class SecretSettingModel(Base):
    __tablename__ = "secret_settings"

    key_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    encrypted_value: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )


class ReindexJobModel(Base):
    __tablename__ = "reindex_jobs"
    __table_args__ = (
        # No maximo uma reindexacao em curso por assistente.
        Index(
            "uq_reindex_jobs_running",
            "assistant_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    assistant_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("assistants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_collection: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    total_documents: Mapped[int] = mapped_column(
        Integer(),
        default=0,
        server_default="0",
        nullable=False,
    )
    processed_documents: Mapped[int] = mapped_column(
        Integer(),
        default=0,
        server_default="0",
        nullable=False,
    )
    error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
