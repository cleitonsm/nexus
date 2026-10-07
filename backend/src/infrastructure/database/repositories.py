from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    ChatMessage,
    Citation,
    Conversation,
    ConversationId,
    Document,
    DocumentId,
    DocumentMetadata,
    MessageId,
    MessageRole,
    ReindexInProgressError,
    ReindexJob,
    ReindexStatus,
)

from .models import (
    AssistantModel,
    ConversationModel,
    DocumentModel,
    MessageModel,
    ReindexJobModel,
    SecretSettingModel,
)


class PostgresAssistantRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, assistant: Assistant) -> Assistant:
        model = self._session.get(AssistantModel, assistant.id.value)
        if model is None:
            model = AssistantModel(
                id=assistant.id.value,
                name=assistant.name.value,
                description=assistant.description,
                initial_prompt=assistant.initial_prompt,
                created_at=assistant.created_at,
            )
            self._session.add(model)
        else:
            model.name = assistant.name.value
            model.description = assistant.description
            model.initial_prompt = assistant.initial_prompt
        self._session.commit()
        self._session.refresh(model)
        return _assistant_to_entity(model)

    def list_all(self) -> list[Assistant]:
        stmt = select(AssistantModel).order_by(
            AssistantModel.created_at.desc()
        )
        return [
            _assistant_to_entity(item)
            for item in self._session.scalars(stmt).all()
        ]

    def get_by_id(self, assistant_id: AssistantId) -> Assistant | None:
        model = self._session.get(AssistantModel, assistant_id.value)
        if model is None:
            return None
        return _assistant_to_entity(model)

    def delete(self, assistant_id: AssistantId) -> bool:
        model = self._session.get(AssistantModel, assistant_id.value)
        if model is None:
            return False
        self._session.delete(model)
        self._session.commit()
        return True


class PostgresConversationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, conversation: Conversation) -> Conversation:
        model = self._session.get(ConversationModel, conversation.id.value)
        if model is None:
            model = ConversationModel(
                id=conversation.id.value,
                assistant_id=conversation.assistant_id.value,
                name=conversation.name,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
            )
            self._session.add(model)
        else:
            model.assistant_id = conversation.assistant_id.value
            model.updated_at = conversation.updated_at
            if conversation.name is not None:
                model.name = conversation.name
        self._session.commit()
        return self.get_by_id(conversation.id) or conversation

    def get_by_id(
        self,
        conversation_id: ConversationId,
    ) -> Conversation | None:
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.id == conversation_id.value)
            .options(selectinload(ConversationModel.messages))
        )
        model = self._session.scalars(stmt).first()
        if model is None:
            return None
        sorted_messages = sorted(
            model.messages,
            key=lambda item: item.created_at,
        )
        messages = tuple(_message_to_entity(item) for item in sorted_messages)
        return Conversation(
            id=ConversationId(model.id),
            assistant_id=AssistantId(model.assistant_id),
            name=model.name,
            created_at=model.created_at,
            updated_at=model.updated_at,
            messages=messages,
        )

    def list_by_assistant(
        self,
        assistant_id: AssistantId,
    ) -> list[Conversation]:
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.assistant_id == assistant_id.value)
            .options(selectinload(ConversationModel.messages))
            .order_by(ConversationModel.updated_at.desc())
        )
        items = self._session.scalars(stmt).all()
        conversations: list[Conversation] = []
        for model in items:
            sorted_messages = sorted(
                model.messages,
                key=lambda message: message.created_at,
            )
            conversations.append(
                Conversation(
                    id=ConversationId(model.id),
                    assistant_id=AssistantId(model.assistant_id),
                    name=model.name,
                    created_at=model.created_at,
                    updated_at=model.updated_at,
                    messages=tuple(
                        _message_to_entity(message)
                        for message in sorted_messages
                    ),
                )
            )
        return conversations

    def save_message(self, message: ChatMessage) -> ChatMessage:
        model = MessageModel(
            id=message.id.value,
            conversation_id=message.conversation_id.value,
            role=message.role.value,
            content=message.content,
            created_at=message.created_at,
            citations=_citations_to_json(message.citations),
        )
        self._session.add(model)
        conversation = self._session.get(
            ConversationModel, message.conversation_id.value
        )
        if conversation is not None:
            conversation.updated_at = message.created_at
            if conversation.name is None and message.role == MessageRole.USER:
                raw = message.content.strip()
                conversation.name = raw[:97] + "..." if len(raw) > 100 else raw
        self._session.commit()
        return _message_to_entity(model)

    def list_messages(
        self,
        conversation_id: ConversationId,
    ) -> list[ChatMessage]:
        stmt = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id.value)
            .order_by(MessageModel.created_at.asc())
        )
        return [
            _message_to_entity(item)
            for item in self._session.scalars(stmt).all()
        ]

    def delete(self, conversation_id: ConversationId) -> bool:
        model = self._session.get(ConversationModel, conversation_id.value)
        if model is None:
            return False
        self._session.delete(model)
        self._session.commit()
        return True


class PostgresDocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, document: Document) -> Document:
        model = self._session.get(DocumentModel, document.id.value)
        if model is None:
            model = DocumentModel(
                id=document.id.value,
                assistant_id=document.assistant_id.value,
                source_name=document.source_name,
                content_hash=document.content_hash,
                metadata_json=json.dumps(document.metadata.values),
                created_at=document.created_at,
                embedding_model=document.embedding_model,
                pipeline_version=document.pipeline_version,
                chunk_count=document.chunk_count,
                storage_key=document.storage_key,
            )
            self._session.add(model)
        else:
            model.assistant_id = document.assistant_id.value
            model.source_name = document.source_name
            model.content_hash = document.content_hash
            model.metadata_json = json.dumps(document.metadata.values)
            model.embedding_model = document.embedding_model
            model.pipeline_version = document.pipeline_version
            model.chunk_count = document.chunk_count
            model.storage_key = document.storage_key
        self._session.commit()
        self._session.refresh(model)
        return _document_to_entity(model)

    def list_by_assistant(self, assistant_id: AssistantId) -> list[Document]:
        stmt = (
            select(DocumentModel)
            .where(DocumentModel.assistant_id == assistant_id.value)
            .order_by(DocumentModel.created_at.desc())
        )
        return [
            _document_to_entity(item)
            for item in self._session.scalars(stmt).all()
        ]


    def delete(self, document_id: DocumentId) -> bool:
        model = self._session.get(DocumentModel, document_id.value)
        if model is None:
            return False
        self._session.delete(model)
        self._session.commit()
        return True


class PostgresReindexJobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, job: ReindexJob) -> ReindexJob:
        model = self._session.get(ReindexJobModel, job.id)
        if model is None:
            model = ReindexJobModel(
                id=job.id,
                assistant_id=job.assistant_id.value,
                started_at=job.started_at,
            )
            self._session.add(model)
        model.target_collection = job.target_collection
        model.status = job.status.value
        model.total_documents = job.total_documents
        model.processed_documents = job.processed_documents
        model.error = job.error
        model.finished_at = job.finished_at
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ReindexInProgressError(
                "a reindex is already in progress for this assistant."
            ) from exc
        self._session.refresh(model)
        return _reindex_job_to_entity(model)

    def get_by_id(self, job_id: str) -> ReindexJob | None:
        model = self._session.get(ReindexJobModel, job_id)
        return _reindex_job_to_entity(model) if model else None

    def get_latest(self, assistant_id: AssistantId) -> ReindexJob | None:
        stmt = (
            select(ReindexJobModel)
            .where(ReindexJobModel.assistant_id == assistant_id.value)
            .order_by(ReindexJobModel.started_at.desc())
            .limit(1)
        )
        model = self._session.scalars(stmt).first()
        return _reindex_job_to_entity(model) if model else None

    def get_running(self, assistant_id: AssistantId) -> ReindexJob | None:
        stmt = select(ReindexJobModel).where(
            ReindexJobModel.assistant_id == assistant_id.value,
            ReindexJobModel.status == ReindexStatus.RUNNING.value,
        )
        model = self._session.scalars(stmt).first()
        return _reindex_job_to_entity(model) if model else None

    def list_running(self) -> list[ReindexJob]:
        stmt = select(ReindexJobModel).where(
            ReindexJobModel.status == ReindexStatus.RUNNING.value
        )
        return [
            _reindex_job_to_entity(item)
            for item in self._session.scalars(stmt).all()
        ]


class PostgresSecretSettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def set_encrypted_value(
        self,
        *,
        key_name: str,
        encrypted_value: str,
    ) -> None:
        now = datetime.now(UTC)
        model = self._session.get(SecretSettingModel, key_name)
        if model is None:
            model = SecretSettingModel(
                key_name=key_name,
                encrypted_value=encrypted_value,
                created_at=now,
                updated_at=now,
            )
            self._session.add(model)
        else:
            model.encrypted_value = encrypted_value
            model.updated_at = now
        self._session.commit()

    def get_encrypted_value(self, *, key_name: str) -> str | None:
        model = self._session.get(SecretSettingModel, key_name)
        if model is None:
            return None
        return model.encrypted_value


def _assistant_to_entity(model: AssistantModel) -> Assistant:
    return Assistant(
        id=AssistantId(model.id),
        name=AssistantName(model.name),
        description=model.description,
        initial_prompt=model.initial_prompt,
        created_at=model.created_at,
    )


def _message_to_entity(model: MessageModel) -> ChatMessage:
    return ChatMessage(
        id=MessageId(model.id),
        conversation_id=ConversationId(model.conversation_id),
        role=MessageRole(model.role),
        content=model.content,
        created_at=model.created_at,
        citations=_citations_from_json(model.citations),
    )


def _citations_to_json(
    citations: tuple[Citation, ...],
) -> list[dict[str, object]] | None:
    if not citations:
        return None
    return [
        {
            "number": item.number,
            "document_id": item.document_id.value,
            "chunk_id": item.chunk_id,
            "source_name": item.source_name,
            "section_path": item.section_path,
            "page": item.page,
            "score": item.score,
            "excerpt": item.excerpt,
        }
        for item in citations
    ]


def _citations_from_json(
    raw: list[dict[str, object]] | None,
) -> tuple[Citation, ...]:
    return tuple(_citation_from_json(item) for item in raw or [])


def _citation_from_json(item: dict[str, object]) -> Citation:
    page = item.get("page")
    return Citation(
        number=int(str(item["number"])),
        document_id=DocumentId(str(item["document_id"])),
        chunk_id=str(item["chunk_id"]),
        source_name=str(item.get("source_name") or ""),
        section_path=str(item.get("section_path") or ""),
        page=page if isinstance(page, int) else None,
        score=float(str(item.get("score") or 0.0)),
        excerpt=str(item["excerpt"]),
    )


def _document_to_entity(model: DocumentModel) -> Document:
    metadata = json.loads(model.metadata_json)
    return Document(
        id=DocumentId(model.id),
        assistant_id=AssistantId(model.assistant_id),
        source_name=model.source_name,
        content_hash=model.content_hash,
        metadata=DocumentMetadata.from_dict(metadata),
        created_at=model.created_at,
        embedding_model=model.embedding_model,
        pipeline_version=model.pipeline_version,
        chunk_count=model.chunk_count,
        storage_key=model.storage_key,
    )


def _reindex_job_to_entity(model: ReindexJobModel) -> ReindexJob:
    return ReindexJob(
        id=model.id,
        assistant_id=AssistantId(model.assistant_id),
        target_collection=model.target_collection,
        status=ReindexStatus(model.status),
        total_documents=model.total_documents,
        processed_documents=model.processed_documents,
        error=model.error,
        started_at=model.started_at,
        finished_at=model.finished_at,
    )
