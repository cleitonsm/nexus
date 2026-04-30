from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from src.application.dto import AssistantDTO
from src.domain import Assistant, AssistantId, AssistantName, AssistantRepository


@dataclass(frozen=True, slots=True)
class CreateAssistantInput:
    name: str
    description: str | None = None
    assistant_id: str | None = None


class CreateAssistantUseCase:
    def __init__(self, repository: AssistantRepository) -> None:
        self._repository = repository

    def execute(self, data: CreateAssistantInput) -> AssistantDTO:
        assistant = Assistant(
            id=AssistantId(data.assistant_id or str(uuid4())),
            name=AssistantName(data.name),
            description=data.description,
        )
        persisted = self._repository.save(assistant)
        return AssistantDTO.from_entity(persisted)
