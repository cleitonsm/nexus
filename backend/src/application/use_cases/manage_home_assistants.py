"""SPEC-016: acesso rapido a assistentes na tela inicial (RF-103 a RF-106)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.application.dto.home_assistants_dto import HomeAssistantsDTO
from src.application.services import AccessControl
from src.domain import (
    ASSISTANT_NOT_AVAILABLE,
    AssistantId,
    AssistantRepository,
    AuthenticatedUser,
    DomainValidationError,
    HomeAssistantPreferenceRepository,
    HomeAssistantSelection,
    HomeAssistantsValidationError,
    effective_home_assistants,
)

logger = logging.getLogger(__name__)


def _visible_ids(
    user: AuthenticatedUser,
    assistants: AssistantRepository,
    access: AccessControl,
) -> list[AssistantId]:
    """RF-42: na ordem em que a lista de assistentes os devolve."""
    return [
        assistant.id
        for assistant, _groups in access.visible_assistants(user, assistants.list_all())
    ]


class GetHomeAssistantsUseCase:
    """RN-49: a selecao gravada filtrada pelo que o usuario ve agora."""

    def __init__(
        self,
        *,
        preferences: HomeAssistantPreferenceRepository,
        assistants: AssistantRepository,
        access_control: AccessControl,
    ) -> None:
        self._preferences = preferences
        self._assistants = assistants
        self._access = access_control

    def execute(self, user: AuthenticatedUser) -> HomeAssistantsDTO:
        visible = _visible_ids(user, self._assistants, self._access)
        saved = self._preferences.get(user.id)
        return HomeAssistantsDTO.from_effective(effective_home_assistants(saved, visible))


@dataclass(frozen=True, slots=True)
class SetHomeAssistantsInput:
    user: AuthenticatedUser
    assistant_ids: tuple[str, ...]
    default_assistant_id: str


class SetHomeAssistantsUseCase:
    """RN-47 e RN-48; o dono e sempre o usuario do token (RF-106)."""

    def __init__(
        self,
        *,
        preferences: HomeAssistantPreferenceRepository,
        assistants: AssistantRepository,
        access_control: AccessControl,
    ) -> None:
        self._preferences = preferences
        self._assistants = assistants
        self._access = access_control

    def execute(self, data: SetHomeAssistantsInput) -> HomeAssistantsDTO:
        try:
            assistant_ids = tuple(AssistantId(item) for item in data.assistant_ids)
            default_id = AssistantId(data.default_assistant_id)
        except DomainValidationError as error:
            # Id em branco nao e de nenhum assistente (RN-48).
            raise HomeAssistantsValidationError(
                "assistant not available.", code=ASSISTANT_NOT_AVAILABLE
            ) from error
        selection = HomeAssistantSelection(assistant_ids=assistant_ids, default_id=default_id)
        visible = _visible_ids(data.user, self._assistants, self._access)
        visible_set = set(visible)
        if any(item not in visible_set for item in selection.assistant_ids):
            # RN-48: inexistente e sem acesso recebem a mesma resposta.
            raise HomeAssistantsValidationError(
                "assistant not available.", code=ASSISTANT_NOT_AVAILABLE
            )
        self._preferences.replace(data.user.id, selection)
        # RN-50: preferencia pessoal, sem auditoria; log sem os ids escolhidos.
        logger.info(
            "home_assistants.saved",
            extra={"user_id": data.user.id, "count": len(selection.assistant_ids)},
        )
        return HomeAssistantsDTO.from_effective(
            effective_home_assistants(selection, visible)
        )
