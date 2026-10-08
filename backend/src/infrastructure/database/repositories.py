from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    AuditEvent,
    AuditQuery,
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
    AssistantGroupModel,
    AssistantModel,
    AuditEventModel,
    ConversationModel,
    DocumentGroupModel,
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
                owner_user_id=conversation.owner_user_id,
            )
            self._session.add(model)
        else:
            # O dono e definido na criacao e nao muda depois (RF-44).
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
        return _conversation_to_entity(model)

    def list_by_assistant(
        self,
        assistant_id: AssistantId,
        owner_user_id: str,
    ) -> list[Conversation]:
        """RN-24: o filtro pelo dono faz parte da consulta."""
        stmt = (
            select(ConversationModel)
            .where(
                ConversationModel.assistant_id == assistant_id.value,
                ConversationModel.owner_user_id == owner_user_id,
            )
            .options(selectinload(ConversationModel.messages))
            .order_by(ConversationModel.updated_at.desc())
        )
        return [
            _conversation_to_entity(model)
            for model in self._session.scalars(stmt).all()
        ]

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

    def get_by_id(self, document_id: DocumentId) -> Document | None:
        model = self._session.get(DocumentModel, document_id.value)
        return _document_to_entity(model) if model else None

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


class PostgresAssistantPermissionRepository:
    """Vinculos de assistentes e de documentos com grupos (RF-42, RF-43)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_assistant_groups(self, assistant_id: AssistantId) -> frozenset[str]:
        stmt = select(AssistantGroupModel.group_name).where(
            AssistantGroupModel.assistant_id == assistant_id.value
        )
        return frozenset(self._session.scalars(stmt).all())

    def list_assistant_groups(self) -> dict[str, frozenset[str]]:
        stmt = select(
            AssistantGroupModel.assistant_id,
            AssistantGroupModel.group_name,
        )
        return _group_by_owner(self._session.execute(stmt).all())

    def set_assistant_groups(
        self,
        assistant_id: AssistantId,
        groups: frozenset[str],
    ) -> None:
        self._session.execute(
            delete(AssistantGroupModel).where(
                AssistantGroupModel.assistant_id == assistant_id.value
            )
        )
        self._session.add_all(
            AssistantGroupModel(assistant_id=assistant_id.value, group_name=group)
            for group in sorted(groups)
        )
        self._session.commit()

    def get_document_groups(self, document_id: DocumentId) -> frozenset[str]:
        stmt = select(DocumentGroupModel.group_name).where(
            DocumentGroupModel.document_id == document_id.value
        )
        return frozenset(self._session.scalars(stmt).all())

    def list_document_groups(
        self,
        assistant_id: AssistantId,
    ) -> dict[str, frozenset[str]]:
        stmt = (
            select(DocumentGroupModel.document_id, DocumentGroupModel.group_name)
            .join(DocumentModel, DocumentModel.id == DocumentGroupModel.document_id)
            .where(DocumentModel.assistant_id == assistant_id.value)
        )
        return _group_by_owner(self._session.execute(stmt).all())

    def set_document_groups(
        self,
        document_id: DocumentId,
        groups: frozenset[str],
    ) -> None:
        self._session.execute(
            delete(DocumentGroupModel).where(
                DocumentGroupModel.document_id == document_id.value
            )
        )
        self._session.add_all(
            DocumentGroupModel(document_id=document_id.value, group_name=group)
            for group in sorted(groups)
        )
        self._session.commit()


class PostgresAuditLogRepository:
    """So inclui e consulta: nao ha operacao de alteracao nem de exclusao."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event: AuditEvent) -> AuditEvent:
        self._session.add(
            AuditEventModel(
                id=event.id,
                occurred_at=event.occurred_at,
                user_id=event.user_id,
                action=event.action,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                details=dict(event.details),
            )
        )
        self._session.commit()
        return event

    def list_events(self, query: AuditQuery) -> list[AuditEvent]:
        stmt = select(AuditEventModel)
        if query.user_id is not None:
            stmt = stmt.where(AuditEventModel.user_id == query.user_id)
        if query.action is not None:
            stmt = stmt.where(AuditEventModel.action == query.action)
        if query.assistant_id is not None:
            stmt = stmt.where(
                AuditEventModel.details["assistant_id"].as_string()
                == query.assistant_id
            )
        if query.occurred_from is not None:
            stmt = stmt.where(AuditEventModel.occurred_at >= query.occurred_from)
        if query.occurred_to is not None:
            stmt = stmt.where(AuditEventModel.occurred_at <= query.occurred_to)
        stmt = (
            stmt.order_by(AuditEventModel.occurred_at.desc(), AuditEventModel.id)
            .limit(query.limit)
            .offset(query.offset)
        )
        return [
            _audit_event_to_entity(item)
            for item in self._session.scalars(stmt).all()
        ]


class PostgresAuditRetentionRepository:
    """Limpeza por retencao (D6), usada so pelo comando de manutencao.

    O gatilho de ``audit_events`` recusa qualquer DELETE, exceto dentro de uma
    transacao que ligue ``nexus.audit_purge``; ``SET LOCAL`` vale so para ela.
    """

    PURGE_SETTING = "SET LOCAL nexus.audit_purge = 'on'"

    def __init__(self, session: Session) -> None:
        self._session = session

    def purge_older_than(self, cutoff: datetime) -> int:
        try:
            self._session.execute(text(self.PURGE_SETTING))
            result = self._session.execute(
                delete(AuditEventModel).where(AuditEventModel.occurred_at < cutoff)
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return int(result.rowcount or 0)


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


def _conversation_to_entity(model: ConversationModel) -> Conversation:
    sorted_messages = sorted(model.messages, key=lambda item: item.created_at)
    return Conversation(
        id=ConversationId(model.id),
        assistant_id=AssistantId(model.assistant_id),
        name=model.name,
        created_at=model.created_at,
        updated_at=model.updated_at,
        messages=tuple(_message_to_entity(item) for item in sorted_messages),
        owner_user_id=model.owner_user_id,
    )


def _group_by_owner(rows: object) -> dict[str, frozenset[str]]:
    grouped: dict[str, set[str]] = {}
    for owner_id, group_name in rows:  # type: ignore[attr-defined]
        grouped.setdefault(owner_id, set()).add(group_name)
    return {owner_id: frozenset(names) for owner_id, names in grouped.items()}


def _audit_event_to_entity(model: AuditEventModel) -> AuditEvent:
    return AuditEvent(
        id=model.id,
        user_id=model.user_id,
        action=model.action,
        resource_type=model.resource_type,
        resource_id=model.resource_id,
        details=dict(model.details or {}),
        occurred_at=model.occurred_at,
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
