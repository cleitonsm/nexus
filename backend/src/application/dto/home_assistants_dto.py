from __future__ import annotations

from dataclasses import dataclass

from src.domain import MAX_HOME_ASSISTANTS, EffectiveHomeAssistants


@dataclass(frozen=True, slots=True)
class HomeAssistantsDTO:
    """SPEC-016: acesso rapido efetivo da tela inicial (RN-49)."""

    assistant_ids: tuple[str, ...]
    default_assistant_id: str | None
    max: int
    customized: bool

    @classmethod
    def from_effective(cls, effective: EffectiveHomeAssistants | None) -> "HomeAssistantsDTO":
        if effective is None:
            return cls((), None, MAX_HOME_ASSISTANTS, False)
        return cls(
            assistant_ids=tuple(item.value for item in effective.assistant_ids),
            default_assistant_id=effective.default_id.value,
            max=MAX_HOME_ASSISTANTS,
            customized=effective.customized,
        )
