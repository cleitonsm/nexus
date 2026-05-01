from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateAssistantRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = None
    initial_prompt: str | None = None


class AssistantResponse(BaseModel):
    id: str
    name: str
    description: str | None
    initial_prompt: str | None
    created_at: datetime
