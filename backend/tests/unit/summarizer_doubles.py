"""SPEC-018: dubles em memoria do resumidor de documentos."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import PurePosixPath

from src.domain import (
    Citation,
    Conversation,
    ConversationDocumentExistsError,
    ConversationId,
    Document,
    DocumentId,
    DocumentStatus,
    DocumentSummary,
    DocumentSummarySection,
    SummaryStage,
)


class Conversations:
    def __init__(self) -> None:
        self.items: dict[str, Conversation] = {}
        self.deleted: list[str] = []

    def save(self, conversation: Conversation) -> Conversation:
        self.items[conversation.id.value] = conversation
        return conversation

    def get_by_id(self, conversation_id: ConversationId, *args, **kwargs) -> Conversation | None:
        return self.items.get(conversation_id.value)

    def delete(self, conversation_id: ConversationId) -> bool:
        self.deleted.append(conversation_id.value)
        return self.items.pop(conversation_id.value, None) is not None


class Documents:
    def __init__(self) -> None:
        self.items: dict[str, Document] = {}
        self.fail_next_save = False

    def save(self, document: Document) -> Document:
        if self.fail_next_save:
            self.fail_next_save = False
            raise RuntimeError("database unavailable")
        if document.conversation_id is not None and any(
            other.conversation_id == document.conversation_id and other.id != document.id
            for other in self.items.values()
        ):
            raise ConversationDocumentExistsError("conversation already has a document.")
        self.items[document.id.value] = document
        return document

    def get_by_id(self, document_id: DocumentId) -> Document | None:
        return self.items.get(document_id.value)

    def delete(self, document_id: DocumentId) -> bool:
        return self.items.pop(document_id.value, None) is not None

    def list_by_assistant(self, assistant_id) -> list[Document]:
        return [
            item
            for item in self.items.values()
            if item.assistant_id == assistant_id and item.status is not DocumentStatus.REPLACED
        ]

    def get_personal_by_conversation(self, conversation_id: ConversationId) -> Document | None:
        return next(
            (item for item in self.items.values() if item.conversation_id == conversation_id),
            None,
        )

    def count_personal_since(self, owner_user_id: str, since: datetime) -> int:
        return sum(
            1
            for item in self.items.values()
            if item.owner_user_id == owner_user_id and item.created_at > since
        )

    def list_personal_to_expire(self, now: datetime, limit: int) -> list[Document]:
        due = sorted(
            (
                item
                for item in self.items.values()
                if item.is_personal
                and item.status is not DocumentStatus.EXPIRED
                and item.expires_at is not None
                and item.expires_at <= now
            ),
            key=lambda item: item.expires_at,
        )
        return due[:limit]


class Summaries:
    def __init__(self) -> None:
        self.items: dict[str, DocumentSummary] = {}
        self.sections: dict[str, dict[int, DocumentSummarySection]] = {}
        self.fail_next_create = False

    def create(self, summary: DocumentSummary) -> DocumentSummary:
        if self.fail_next_create:
            self.fail_next_create = False
            raise RuntimeError("database unavailable")
        self.items[summary.document_id.value] = summary
        return summary

    def get(self, document_id: DocumentId) -> DocumentSummary | None:
        return self.items.get(document_id.value)

    def set_stage(self, document_id, stage, *, batches_done=0, batches_total=0, document_tokens=None):
        current = self.items[document_id.value]
        self.items[document_id.value] = replace(
            current,
            stage=stage,
            batches_done=batches_done,
            batches_total=batches_total,
            failure_code=None,
            document_tokens=document_tokens if document_tokens is not None else current.document_tokens,
        )

    def save_section(self, section: DocumentSummarySection) -> None:
        self.sections.setdefault(section.document_id.value, {})[section.position] = section

    def list_sections(self, document_id: DocumentId) -> list[DocumentSummarySection]:
        found = self.sections.get(document_id.value, {})
        return [found[key] for key in sorted(found)]

    def complete(self, document_id, *, content, citations: tuple[Citation, ...], prompt_version, model):
        self.items[document_id.value] = replace(
            self.items[document_id.value],
            stage=SummaryStage.READY,
            content=content,
            citations=citations,
            prompt_version=prompt_version,
            model=model,
            failure_code=None,
        )

    def fail(self, document_id, failure_code: str) -> None:
        self.items[document_id.value] = replace(
            self.items[document_id.value], stage=SummaryStage.FAILED, failure_code=failure_code
        )

    def delete_content(self, document_id: DocumentId) -> None:
        self.sections.pop(document_id.value, None)
        self.items[document_id.value] = replace(
            self.items[document_id.value], stage=SummaryStage.EXPIRED, content=None, citations=()
        )


class Storage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def save(self, *, assistant_id, document_id, filename, content) -> str:
        key = f"{assistant_id.value}/{document_id.value}/{filename}"
        self.files[key] = content
        return key

    def load(self, storage_key: str) -> bytes:
        return self.files[storage_key]

    def delete(self, storage_key: str) -> None:
        self.deleted.append(storage_key)
        self.files.pop(storage_key, None)


class VectorStore:
    def __init__(self) -> None:
        self.deleted: list[tuple[str, str]] = []
        self.fail_delete = False

    def delete_by_document(self, collection_name, document_id) -> None:
        if self.fail_delete:
            raise RuntimeError("qdrant unavailable")
        self.deleted.append((collection_name.value, document_id.value))


class Indexer:
    """So o ``supports`` da ingestao: decide pela extensao."""

    formats = (".txt", ".md", ".markdown", ".pdf", ".doc", ".docx")

    def supports(self, *, source_name: str, content_type: str | None) -> bool:
        return PurePosixPath(source_name).suffix.lower() in self.formats
