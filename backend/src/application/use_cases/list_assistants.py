from __future__ import annotations

from src.application.dto import AssistantDTO
from src.domain import AssistantRepository


class ListAssistantsUseCase:
    def __init__(self, repository: AssistantRepository) -> None:
        self._repository = repository

    def execute(self) -> list[AssistantDTO]:
        assistants = self._repository.list_all()
        return [AssistantDTO.from_entity(item) for item in assistants]
