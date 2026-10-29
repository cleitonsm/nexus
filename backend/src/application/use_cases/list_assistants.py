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
                # SPEC-017 (D5): o prompt so vai para quem pode edita-lo.
                reveal_prompt=self._access.can_edit_assistant(user, groups),
            )
            for assistant, groups in visible
        ]

    def inference_catalog(self, user: AuthenticatedUser) -> list[AssistantDTO]:
        """Candidatos da escolha automatica (RF-42), com o prompt de cada um.

        Uso interno: o catalogo vai so ao LLM, nunca na resposta HTTP. A D5 da
        SPEC-017 esconde o prompt da listagem, nao da inferencia.
        """
        visible = self._access.visible_assistants(user, self._repository.list_all())
        return [
            AssistantDTO.from_entity(assistant, reveal_prompt=True)
            for assistant, _groups in visible
        ]
