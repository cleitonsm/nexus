from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    assistant_id: str = Field(min_length=1)


class ConversationResponse(BaseModel):
    id: str
    assistant_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class MessageRoleRequest(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AddMessageRequest(BaseModel):
    role: MessageRoleRequest
    content: str = Field(min_length=1)


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime


class ConversationDetailResponse(BaseModel):
    id: str
    assistant_id: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse]
