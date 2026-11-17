"""SPEC-018: respostas do resumidor de documentos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain import (
    Document,
    DocumentSummary,
    SummarizerCapabilities,
    SummaryProgress,
    capabilities_markdown,
)

from .conversation_dto import CitationDTO


@dataclass(frozen=True, slots=True)
class SummarizerInfoDTO:
    """RF-119 e D37: finalidade e limites, montados das constantes."""

    assistant_id: str
    formats: tuple[str, ...]
    max_bytes: int
    max_megabytes_label: str
    max_tokens: int
    pages_hint: str
    retention_days: int
    daily_limit: int
    out_of_scope: tuple[str, ...]
    welcome_markdown: str

    @classmethod
    def from_capabilities(
        cls, assistant_id: str, capabilities: SummarizerCapabilities
    ) -> "SummarizerInfoDTO":
        return cls(
            assistant_id=assistant_id,
            formats=capabilities.formats,
            max_bytes=capabilities.max_bytes,
            max_megabytes_label=capabilities.max_megabytes_label,
            max_tokens=capabilities.max_tokens,
            pages_hint=capabilities.pages_hint,
            retention_days=capabilities.retention_days,
            daily_limit=capabilities.daily_limit,
            out_of_scope=capabilities.out_of_scope,
            welcome_markdown=capabilities_markdown(capabilities, reason="welcome"),
        )


@dataclass(frozen=True, slots=True)
class SummaryDocumentDTO:
    """RF-115 e D36: o documento da conversa e a etapa visivel."""

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

    @classmethod
    def build(cls, document: Document, progress: SummaryProgress) -> "SummaryDocumentDTO":
        return cls(
            document_id=document.id.value,
            conversation_id=document.conversation_id.value if document.conversation_id else "",
            source_name=document.source_name,
            size_bytes=document.size_bytes,
            stage=progress.stage.value,
            done=progress.done,
            total=progress.total,
            failure_code=progress.failure_code,
            failure_detail=progress.failure_detail,
            questions_available=progress.questions_available,
            created_at=document.created_at,
            expires_at=document.expires_at,
        )


@dataclass(frozen=True, slots=True)
class StoredSummaryDTO:
    """RF-117 e RNF-37: o resumo gravado, sem chamar o LLM."""

    document_id: str
    content: str
    citations: tuple[CitationDTO, ...]
    prompt_version: str | None
    model: str | None
    updated_at: datetime

    @classmethod
    def from_entity(cls, summary: DocumentSummary) -> "StoredSummaryDTO":
        return cls(
            document_id=summary.document_id.value,
            content=summary.content or "",
            citations=tuple(CitationDTO.from_entity(item) for item in summary.citations),
            prompt_version=summary.prompt_version,
            model=summary.model,
            updated_at=summary.updated_at,
        )
