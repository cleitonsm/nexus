from __future__ import annotations

from src.application.dto import AssistantDTO
from src.application.services import AccessControl
from src.domain import AssistantRepository, AuthenticatedUser


class ListAssistantsUseCase:
    """RF-42: cada usuario ve apenas os assistentes dos seus grupos."""

    def __init__(
        self,
        repository: AssistantRepository,
        access_control: AccessControl,
    ) -> None:
        self._repository = repository
        self._access = access_control

    def execute(self, user: AuthenticatedUser) -> list[AssistantDTO]:
        visible = self._access.visible_assistants(user, self._repository.list_all())
        return [
            AssistantDTO.from_entity(
                assistant,
                # Os grupos so interessam a quem gerencia o assistente.
                groups
                if self._access.can_manage_documents(user, groups)
                else frozenset(),
            )
            for assistant, groups in visible
        ]
