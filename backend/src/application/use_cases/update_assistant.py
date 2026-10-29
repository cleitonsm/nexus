"""SPEC-017: edicao de nome, descricao e prompt do assistente."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from src.application.dto import AssistantDTO
from src.application.services import AccessControl
from src.domain import (
    Assistant,
    AssistantId,
    AssistantProfile,
    AssistantRepository,
    AuditAction,
    AuditResource,
    AuthenticatedUser,
    assistant_profile_changes,
    build_assistant_profile,
)

from .manage_assistant_access import AssistantNotFoundError


@dataclass(frozen=True, slots=True)
class UpdateAssistantInput:
    user: AuthenticatedUser
    assistant_id: str
    name: str
    description: str | None = None
    initial_prompt: str | None = None


def _text_digest(value: str | None) -> dict[str, object]:
    """D6: tamanho e SHA-256, nunca o texto (RN-53)."""
    if value is None:
        return {"length": 0, "sha256": None}
    return {
        "length": len(value),
        "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
    }


def _profile_of(assistant: Assistant) -> AssistantProfile:
    return AssistantProfile(
        name=assistant.name,
        description=assistant.description,
        initial_prompt=assistant.initial_prompt,
    )


class UpdateAssistantUseCase:
    """RF-108: altera nome, descricao e prompt sem tocar grupos, base nem LLM.

    Edita o administrador ou o curador do assistente (D1, RN-52). A ultima
    gravacao vence (D7).
    """

    def __init__(
        self,
        repository: AssistantRepository,
        access_control: AccessControl,
    ) -> None:
        self._repository = repository
        self._access = access_control

    def execute(self, data: UpdateAssistantInput) -> AssistantDTO:
        assistant_id = AssistantId(data.assistant_id)
        groups = self._access.require_assistant_edit(
            data.user, assistant_id, AuditAction.ASSISTANT_UPDATED
        )
        current = self._repository.get_by_id(assistant_id)
        if current is None:
            raise AssistantNotFoundError(assistant_id.value)
        before = _profile_of(current)
        after = build_assistant_profile(
            data.name, data.description, data.initial_prompt
        )
        changed = assistant_profile_changes(before, after)
        if not changed:
            return AssistantDTO.from_entity(current, groups)
        updated = self._repository.update_profile(
            assistant_id,
            name=after.name,
            description=after.description,
            initial_prompt=after.initial_prompt,
        )
        if updated is None:
            # RN-54: excluido entre a leitura e a gravacao; nada foi recriado.
            raise AssistantNotFoundError(assistant_id.value)
        self._access.audit(
            data.user,
            AuditAction.ASSISTANT_UPDATED,
            resource_type=AuditResource.ASSISTANT,
            resource_id=assistant_id.value,
            details={
                "assistant_id": assistant_id.value,
                "changed_fields": list(changed),
                "name_before": before.name.value,
                "name_after": after.name.value,
                "description_before": _text_digest(before.description),
                "description_after": _text_digest(after.description),
                "initial_prompt_before": _text_digest(before.initial_prompt),
                "initial_prompt_after": _text_digest(after.initial_prompt),
            },
        )
        return AssistantDTO.from_entity(updated, groups)
