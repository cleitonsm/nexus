from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain import Assistant


@dataclass(frozen=True, slots=True)
class AssistantDTO:
    id: str
    name: str
    description: str | None
    initial_prompt: str | None
    created_at: datetime

    @classmethod
    def from_entity(cls, assistant: Assistant) -> "AssistantDTO":
        return cls(
            id=assistant.id.value,
            name=assistant.name.value,
            description=assistant.description,
            initial_prompt=assistant.initial_prompt,
            created_at=assistant.created_at,
        )
