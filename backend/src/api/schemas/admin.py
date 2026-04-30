from pydantic import BaseModel, Field


class SaveApiKeyRequest(BaseModel):
    api_key: str = Field(min_length=1)


class ApiKeyStatusResponse(BaseModel):
    configured: bool
