from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# SPEC-017: teto contra corpos enormes, acima dos limites do dominio (RN-51),
# para que o 422 traga o ``code`` da regra e nao o erro generico do Pydantic.
_BODY_CEILING = 20_000


class CreateAssistantRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=_BODY_CEILING)
    initial_prompt: str | None = Field(default=None, max_length=_BODY_CEILING)


class UpdateAssistantRequest(BaseModel):
    """SPEC-017: substitui os tres campos (PUT)."""

    name: str = Field(max_length=_BODY_CEILING)
    description: str | None = Field(default=None, max_length=_BODY_CEILING)
    initial_prompt: str | None = Field(default=None, max_length=_BODY_CEILING)


class InferAssistantRequest(BaseModel):
    question: str = Field(min_length=1)


class InferAssistantResponse(BaseModel):
    assistant_id: str | None


class AssistantResponse(BaseModel):
    id: str
    name: str
    description: str | None
    initial_prompt: str | None
    created_at: datetime
    # Grupos vinculados; vazio para quem nao gerencia o assistente.
    groups: list[str] = Field(default_factory=list)
