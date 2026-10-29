"""Nome, descricao e prompt inicial do assistente (SPEC-017, RN-51).

Os limites valem na criacao e na edicao. Ficam fora da entidade ``Assistant``
para que a leitura de um assistente gravado antes deles nunca falhe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .errors import DomainValidationError
from .value_objects import AssistantName

MAX_ASSISTANT_NAME: Final = 80
MAX_ASSISTANT_DESCRIPTION: Final = 500
MAX_ASSISTANT_PROMPT: Final = 4000

ASSISTANT_NAME_REQUIRED: Final = "assistant_name_required"
ASSISTANT_NAME_TOO_LONG: Final = "assistant_name_too_long"
ASSISTANT_DESCRIPTION_TOO_LONG: Final = "assistant_description_too_long"
ASSISTANT_PROMPT_TOO_LONG: Final = "assistant_prompt_too_long"

PROFILE_FIELDS: Final = ("name", "description", "initial_prompt")


class AssistantProfileValidationError(DomainValidationError):
    """RN-51: campo invalido; ``code`` vira o ``code`` do 422."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def normalize_optional_text(value: str | None) -> str | None:
    """D4: vazio ou so espacos vira ``None``; o resto perde os espacos das pontas."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


@dataclass(frozen=True, slots=True)
class AssistantProfile:
    """Os tres campos editaveis, ja normalizados e dentro dos limites."""

    name: AssistantName
    description: str | None
    initial_prompt: str | None


def build_assistant_profile(
    name: str,
    description: str | None,
    initial_prompt: str | None,
) -> AssistantProfile:
    """Valida e normaliza os campos (RN-51), com o ``code`` de cada regra."""
    stripped_name = (name or "").strip()
    if not stripped_name:
        raise AssistantProfileValidationError(
            "assistant name is required.", code=ASSISTANT_NAME_REQUIRED
        )
    if len(stripped_name) > MAX_ASSISTANT_NAME:
        raise AssistantProfileValidationError(
            f"assistant name must be at most {MAX_ASSISTANT_NAME} characters.",
            code=ASSISTANT_NAME_TOO_LONG,
        )
    normalized_description = normalize_optional_text(description)
    if (
        normalized_description is not None
        and len(normalized_description) > MAX_ASSISTANT_DESCRIPTION
    ):
        raise AssistantProfileValidationError(
            "assistant description must be at most "
            f"{MAX_ASSISTANT_DESCRIPTION} characters.",
            code=ASSISTANT_DESCRIPTION_TOO_LONG,
        )
    normalized_prompt = normalize_optional_text(initial_prompt)
    if normalized_prompt is not None and len(normalized_prompt) > MAX_ASSISTANT_PROMPT:
        raise AssistantProfileValidationError(
            f"assistant prompt must be at most {MAX_ASSISTANT_PROMPT} characters.",
            code=ASSISTANT_PROMPT_TOO_LONG,
        )
    return AssistantProfile(
        name=AssistantName(stripped_name),
        description=normalized_description,
        initial_prompt=normalized_prompt,
    )


def assistant_profile_changes(
    before: AssistantProfile,
    after: AssistantProfile,
) -> tuple[str, ...]:
    """Campos alterados, na ordem de ``PROFILE_FIELDS`` (RN-53)."""
    changed: list[str] = []
    if before.name.value != after.name.value:
        changed.append("name")
    if before.description != after.description:
        changed.append("description")
    if before.initial_prompt != after.initial_prompt:
        changed.append("initial_prompt")
    return tuple(changed)
