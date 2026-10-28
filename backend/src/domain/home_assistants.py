"""SPEC-016: acesso rapido a assistentes na tela inicial.

Regras puras: a selecao gravada pelo usuario (RN-47) e o acesso rapido efetivo,
calculado contra os assistentes que ele pode usar agora (RN-49, D4, D8).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from .errors import DomainValidationError
from .value_objects import AssistantId

# D1: limite escolhido pelo autor em 2026-10-28. Fica no dominio para mudar
# sem migracao.
MAX_HOME_ASSISTANTS: Final = 4

HOME_ASSISTANTS_EMPTY: Final = "home_assistants_empty"
HOME_ASSISTANTS_LIMIT: Final = "home_assistants_limit"
HOME_ASSISTANTS_DUPLICATE: Final = "home_assistants_duplicate"
HOME_ASSISTANTS_DEFAULT_NOT_SELECTED: Final = "home_assistants_default_not_selected"
ASSISTANT_NOT_AVAILABLE: Final = "assistant_not_available"


class HomeAssistantsValidationError(DomainValidationError):
    """RN-47/RN-48: selecao invalida; ``code`` vira o ``code`` do 422."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class HomeAssistantSelection:
    """Selecao gravada: ids na ordem de marcacao (D7) e o padrao (RN-47)."""

    assistant_ids: tuple[AssistantId, ...]
    default_id: AssistantId

    def __post_init__(self) -> None:
        ids = tuple(self.assistant_ids)
        object.__setattr__(self, "assistant_ids", ids)
        if not ids:
            raise HomeAssistantsValidationError(
                "select at least one assistant.", code=HOME_ASSISTANTS_EMPTY
            )
        if len(ids) > MAX_HOME_ASSISTANTS:
            raise HomeAssistantsValidationError(
                f"select at most {MAX_HOME_ASSISTANTS} assistants.",
                code=HOME_ASSISTANTS_LIMIT,
            )
        if len(set(ids)) != len(ids):
            raise HomeAssistantsValidationError(
                "assistants must not repeat.", code=HOME_ASSISTANTS_DUPLICATE
            )
        if self.default_id not in ids:
            raise HomeAssistantsValidationError(
                "the default assistant must be one of the selected.",
                code=HOME_ASSISTANTS_DEFAULT_NOT_SELECTED,
            )

    @property
    def display_order(self) -> tuple[AssistantId, ...]:
        """D7: padrao primeiro, os outros na ordem de marcacao."""
        return (self.default_id,) + tuple(
            item for item in self.assistant_ids if item != self.default_id
        )


@dataclass(frozen=True, slots=True)
class EffectiveHomeAssistants:
    """O que a tela inicial mostra agora (RN-49)."""

    assistant_ids: tuple[AssistantId, ...]
    default_id: AssistantId
    customized: bool


def effective_home_assistants(
    saved: HomeAssistantSelection | None,
    visible: Sequence[AssistantId],
) -> EffectiveHomeAssistants | None:
    """RN-49, D4 e D8. ``None`` so quando o usuario nao ve nenhum assistente."""
    if not visible:
        return None
    visible_set = set(visible)
    if saved is not None:
        kept = tuple(item for item in saved.assistant_ids if item in visible_set)
        if kept:
            if saved.default_id in kept:
                default_id = saved.default_id
                ordered = tuple(
                    item for item in saved.display_order if item in visible_set
                )
            else:
                # D8: o padrao sumiu; o primeiro que sobrou assume.
                default_id, ordered = kept[0], kept
            return EffectiveHomeAssistants(
                assistant_ids=ordered, default_id=default_id, customized=True
            )
    first = tuple(dict.fromkeys(visible))[:MAX_HOME_ASSISTANTS]
    return EffectiveHomeAssistants(
        assistant_ids=first, default_id=first[0], customized=False
    )
