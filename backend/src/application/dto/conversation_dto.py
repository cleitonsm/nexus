from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain import ChatMessage, Citation, Conversation


@dataclass(frozen=True, slots=True)
class ConversationDTO:
    id: str
    assistant_id: str
    name: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int

    @classmethod
    def from_entity(cls, conversation: Conversation) -> "ConversationDTO":
        return cls(
            id=conversation.id.value,
            assistant_id=conversation.assistant_id.value,
            name=conversation.name,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=len(conversation.messages),
        )


@dataclass(frozen=True, slots=True)
class RegisterConversationResult:
    conversation: ConversationDTO


@dataclass(frozen=True, slots=True)
class ListConversationsResult:
    conversations: list[ConversationDTO]


@dataclass(frozen=True, slots=True)
class CitationDTO:
    number: int
    document_id: str
    chunk_id: str
    source_name: str
    section_path: str
    page: int | None
    score: float
    excerpt: str
    # Falso quando o documento citado foi excluido ou substituido (RN-29, D10).
    document_available: bool = True

    @classmethod
    def from_entity(
        cls,
        citation: Citation,
        *,
        removed_documents: frozenset[str] = frozenset(),
    ) -> "CitationDTO":
        return cls(
            number=citation.number,
            document_id=citation.document_id.value,
            chunk_id=citation.chunk_id,
            source_name=citation.source_name,
            section_path=citation.section_path,
            page=citation.page,
            score=citation.score,
            excerpt=citation.excerpt,
            document_available=citation.document_id.value not in removed_documents,
        )


@dataclass(frozen=True, slots=True)
class MessageDTO:
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime
    citations: tuple[CitationDTO, ...] = ()

    @classmethod
    def from_entity(
        cls,
        message: ChatMessage,
        *,
        removed_documents: frozenset[str] = frozenset(),
    ) -> "MessageDTO":
        return cls(
            id=message.id.value,
            conversation_id=message.conversation_id.value,
            role=message.role.value,
            content=message.content,
            created_at=message.created_at,
            citations=tuple(
                CitationDTO.from_entity(item, removed_documents=removed_documents)
                for item in message.citations
            ),
        )


@dataclass(frozen=True, slots=True)
class ChatTurnResult:
    conversation_id: str
    assistant_id: str
    user_message: MessageDTO
    assistant_message: MessageDTO
    used_context_chunks: int
    fallback_used: bool
    rewritten_query: str = ""

    @property
    def citations(self) -> tuple[CitationDTO, ...]:
        return self.assistant_message.citations


@dataclass(frozen=True, slots=True)
class ChatStreamEvent:
    """Evento da resposta em streaming (RF-58).

    ``delta``: parte nova do texto. ``replace``: texto final diferente do que
    foi transmitido (fallback ou marcador invalido removido), que substitui o
    exibido. ``done``: resultado completo, com as citacoes.
    """

    kind: str
    text: str = ""
    result: ChatTurnResult | None = None
