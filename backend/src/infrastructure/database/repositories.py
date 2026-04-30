from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    ChatMessage,
    Conversation,
    ConversationId,
    Document,
    DocumentId,
    DocumentMetadata,
    MessageId,
    MessageRole,
)

from .models import (
    AssistantModel,
    ConversationModel,
    DocumentModel,
    MessageModel,
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
                created_at=assistant.created_at,
            )
            self._session.add(model)
        else:
            model.name = assistant.name.value
            model.description = assistant.description
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


class PostgresConversationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, conversation: Conversation) -> Conversation:
        model = self._session.get(ConversationModel, conversation.id.value)
        if model is None:
            model = ConversationModel(
                id=conversation.id.value,
                assistant_id=conversation.assistant_id.value,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
            )
            self._session.add(model)
        else:
            model.assistant_id = conversation.assistant_id.value
            model.updated_at = conversation.updated_at
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
            created_at=model.created_at,
            updated_at=model.updated_at,
            messages=messages,
        )

    def save_message(self, message: ChatMessage) -> ChatMessage:
        model = MessageModel(
            id=message.id.value,
            conversation_id=message.conversation_id.value,
            role=message.role.value,
            content=message.content,
            created_at=message.created_at,
        )
        self._session.add(model)
        conversation = self._session.get(
            ConversationModel, message.conversation_id.value
        )
        if conversation is not None:
            conversation.updated_at = message.created_at
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
            )
            self._session.add(model)
        else:
            model.assistant_id = document.assistant_id.value
            model.source_name = document.source_name
            model.content_hash = document.content_hash
            model.metadata_json = json.dumps(document.metadata.values)
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
        created_at=model.created_at,
    )


def _message_to_entity(model: MessageModel) -> ChatMessage:
    return ChatMessage(
        id=MessageId(model.id),
        conversation_id=ConversationId(model.conversation_id),
        role=MessageRole(model.role),
        content=model.content,
        created_at=model.created_at,
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
    )
