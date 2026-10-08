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
    # Grupos vinculados (RF-42); preenchido so para quem gerencia o assistente.
    groups: tuple[str, ...] = ()

    @classmethod
    def from_entity(
        cls,
        assistant: Assistant,
        groups: frozenset[str] = frozenset(),
    ) -> "AssistantDTO":
        return cls(
            id=assistant.id.value,
            name=assistant.name.value,
            description=assistant.description,
            initial_prompt=assistant.initial_prompt,
            created_at=assistant.created_at,
            groups=tuple(sorted(groups)),
        )
