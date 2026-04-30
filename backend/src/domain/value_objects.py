from __future__ import annotations

from dataclasses import dataclass
from re import sub
from typing import Any

from .errors import DomainValidationError


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise DomainValidationError(f"{field_name} must not be empty.")
    return normalized


@dataclass(frozen=True, slots=True)
class AssistantId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _require_non_empty(self.value, "assistant_id"))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class DocumentId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _require_non_empty(self.value, "document_id"))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class ConversationId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _require_non_empty(self.value, "conversation_id"))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class MessageId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _require_non_empty(self.value, "message_id"))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class AssistantName:
    value: str

    def __post_init__(self) -> None:
        normalized = _require_non_empty(self.value, "assistant_name")
        if len(normalized) > 80:
            raise DomainValidationError("assistant_name must be at most 80 characters.")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class CollectionName:
    value: str

    def __post_init__(self) -> None:
        normalized = _require_non_empty(self.value, "collection_name").lower()
        cleaned = sub(r"[^a-z0-9_-]+", "-", normalized).strip("-")
        if not cleaned:
            raise DomainValidationError("collection_name must contain valid characters.")
        if len(cleaned) > 63:
            raise DomainValidationError("collection_name must be at most 63 characters.")
        object.__setattr__(self, "value", cleaned)

    @classmethod
    def from_assistant_id(cls, assistant_id: AssistantId) -> "CollectionName":
        return cls(value=f"assistant-{assistant_id.value}")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    values: dict[str, str]

    def __post_init__(self) -> None:
        normalized: dict[str, str] = {}
        for key, value in self.values.items():
            key_str = _require_non_empty(str(key), "document_metadata.key")
            value_str = _require_non_empty(str(value), f"document_metadata.{key_str}")
            normalized[key_str] = value_str
        object.__setattr__(self, "values", normalized)

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "DocumentMetadata":
        if not value:
            return cls(values={})
        return cls(values={key: str(raw_value) for key, raw_value in value.items()})
