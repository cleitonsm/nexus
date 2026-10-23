from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from src.application.dto import AssistantDTO
from src.application.services import AccessControl
from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    AssistantRepository,
    AuditAction,
    AuditResource,
    AuthenticatedUser,
)


@dataclass(frozen=True, slots=True)
class CreateAssistantInput:
    user: AuthenticatedUser
    name: str
    description: str | None = None
    initial_prompt: str | None = None
    assistant_id: str | None = None


class CreateAssistantUseCase:
    """RN-21: so o administrador cria assistentes.

    O assistente nasce sem grupo: fica visivel apenas a administradores ate
    ser vinculado (RN-22).
    """

    def __init__(
        self,
        repository: AssistantRepository,
        access_control: AccessControl,
    ) -> None:
        self._repository = repository
        self._access = access_control

    def execute(self, data: CreateAssistantInput) -> AssistantDTO:
        self._access.require_admin(data.user, AuditAction.ASSISTANT_CREATED)
        assistant = Assistant(
            id=AssistantId(data.assistant_id or str(uuid4())),
            name=AssistantName(data.name),
            description=data.description,
            initial_prompt=data.initial_prompt,
        )
        persisted = self._repository.save(assistant)
        self._access.audit(
            data.user,
            AuditAction.ASSISTANT_CREATED,
            resource_type=AuditResource.ASSISTANT,
            resource_id=persisted.id.value,
            details={
                "assistant_id": persisted.id.value,
                "assistant_name": persisted.name.value,
            },
        )
        return AssistantDTO.from_entity(persisted)
