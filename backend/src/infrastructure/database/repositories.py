from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    ChatMessage,
    Conversation,
    ConversationId,
    MessageId,
    MessageRole,
)

from .models import AssistantModel, ConversationModel, MessageModel


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
        stmt = select(AssistantModel).order_by(AssistantModel.created_at.desc())
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

    def get_by_id(self, conversation_id: ConversationId) -> Conversation | None:
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.id == conversation_id.value)
            .options(selectinload(ConversationModel.messages))
        )
        model = self._session.scalars(stmt).first()
        if model is None:
            return None
        sorted_messages = sorted(model.messages, key=lambda item: item.created_at)
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

    def list_messages(self, conversation_id: ConversationId) -> list[ChatMessage]:
        stmt = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id.value)
            .order_by(MessageModel.created_at.asc())
        )
        return [
            _message_to_entity(item)
            for item in self._session.scalars(stmt).all()
        ]


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
