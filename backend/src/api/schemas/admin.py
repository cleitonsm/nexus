from pydantic import BaseModel, Field


class SaveApiKeyRequest(BaseModel):
    api_key: str = Field(min_length=1)


class ApiKeyStatusResponse(BaseModel):
    configured: bool


class ApiKeyTestResponse(BaseModel):
    ok: bool
    model: str
    message: str
    response_preview: str
