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
    """Papeis aceitos de fora: so ``user`` (SPEC-007 fix-1).

    ``assistant`` e ``system`` sao gerados pelo servidor; aceitar de fora
    permitiria forjar resposta do assistente no historico.
    """

    USER = "user"


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
    # Falso quando o documento foi excluido ou substituido (RN-29).
    document_available: bool = True


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


class SummarizerInfoResponse(BaseModel):
    """SPEC-018 (RF-119, D37): finalidade e limites do resumidor."""

    assistant_id: str
    formats: list[str]
    max_bytes: int
    max_megabytes_label: str
    max_tokens: int
    pages_hint: str
    retention_days: int
    daily_limit: int
    out_of_scope: list[str]
    welcome_markdown: str


class SummaryDocumentResponse(BaseModel):
    """SPEC-018 (RF-115, D36): o documento da conversa e a etapa visivel."""

    document_id: str
    conversation_id: str
    source_name: str
    size_bytes: int | None
    stage: str
    done: int
    total: int
    failure_code: str | None
    failure_detail: str | None
    questions_available: bool
    created_at: datetime
    expires_at: datetime | None


class StoredSummaryResponse(BaseModel):
    """SPEC-018 (RF-117, RNF-37): o resumo gravado, sem LLM."""

    document_id: str
    content: str
    citations: list[CitationResponse]
    prompt_version: str | None
    model: str | None
    updated_at: datetime
