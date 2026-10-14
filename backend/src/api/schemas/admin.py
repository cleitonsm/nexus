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


class LLMSettingsRequest(BaseModel):
    """SPEC-008 RF-69: ``api_url`` so vale para o provedor ``custom``."""

    provider: str = Field(min_length=1, max_length=20)
    model: str = Field(min_length=1, max_length=200)
    api_url: str | None = Field(default=None, max_length=2048)


class LLMSettingsResponse(BaseModel):
    provider: str
    model: str
    api_url: str
    source: str
    # Presets conhecidos, para a tela preencher a URL sem duplicar a lista.
    provider_urls: dict[str, str]
