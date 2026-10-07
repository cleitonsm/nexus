from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    assistant_id: str = Field(min_length=1)


class ConversationResponse(BaseModel):
    id: str
    assistant_id: str
    name: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int


class ConversationHistoryResponse(BaseModel):
    id: str
    assistant_id: str
    name: str | None
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


class CitationResponse(BaseModel):
    number: int
    document_id: str
    chunk_id: str
    source_name: str
    section_path: str
    page: int | None
    score: float
    excerpt: str


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime
    citations: list[CitationResponse] = Field(default_factory=list)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    # Teto por pergunta: reduz a quantidade de trechos abaixo de
    # RERANK_TOP_N, nunca acima (SPEC-003).
    top_k: int | None = Field(default=None, ge=1, le=20)


class ChatResponse(BaseModel):
    conversation_id: str
    assistant_id: str
    user_message: MessageResponse
    assistant_message: MessageResponse
    used_context_chunks: int
    fallback_used: bool
    citations: list[CitationResponse] = Field(default_factory=list)
    rewritten_query: str = ""


class ConversationDetailResponse(BaseModel):
    id: str
    assistant_id: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse]
