"""Schemas da SPEC-013: credenciais de LLM e configuracao do assistente.

A chave so entra (``api_key``), nunca sai: as respostas trazem
``key_configured`` (RN-39). Os campos da chave nao aparecem em ``repr``.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, StrictBool, StrictInt


class LLMModelPayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    # D8: preco opcional por 1K tokens, entrada e saida juntos.
    input_per_1k: Decimal | None = Field(default=None, ge=0)
    output_per_1k: Decimal | None = Field(default=None, ge=0)


class CreateLLMCredentialRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=20)
    # So vale para ``custom`` (D5); nos presets a URL e a do provedor.
    api_url: str | None = Field(default=None, max_length=2048)
    models: list[LLMModelPayload] = Field(min_length=1)
    default_model: str = Field(min_length=1, max_length=200)
    api_key: str = Field(min_length=1, repr=False)
    make_default: bool = False


class UpdateLLMCredentialRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=20)
    api_url: str | None = Field(default=None, max_length=2048)
    models: list[LLMModelPayload] = Field(min_length=1)
    default_model: str = Field(min_length=1, max_length=200)
    # Vazia mantem a chave; obrigatoria quando provedor ou URL mudam (D12).
    api_key: str | None = Field(default=None, repr=False)


class LLMModelResponse(BaseModel):
    name: str
    input_per_1k: Decimal | None = None
    output_per_1k: Decimal | None = None


class LLMCredentialResponse(BaseModel):
    id: str
    name: str
    provider: str
    api_url: str
    models: list[LLMModelResponse]
    default_model: str
    is_default: bool
    key_configured: bool
    assistant_ids: list[str] = Field(default_factory=list)
    following_assistant_ids: list[str] = Field(default_factory=list)


class LLMCredentialListResponse(BaseModel):
    items: list[LLMCredentialResponse]
    # Presets conhecidos (D5), para a tela preencher a URL.
    provider_urls: dict[str, str]
    # Moeda dos precos (``LLM_PRICE_CURRENCY``); sem preco, vale o ambiente.
    currency: str


class LLMCredentialOptionResponse(BaseModel):
    id: str
    name: str
    provider: str
    models: list[str]
    default_model: str
    is_default: bool


class DefaultChangeImpactRequest(BaseModel):
    # Simula outra lista de modelos (edicao em curso); vazio = a gravada.
    model_names: list[str] | None = None


class DefaultChangeImpactResponse(BaseModel):
    credential_id: str
    following_assistant_ids: list[str]
    falling_back_assistant_ids: list[str]


class TestLLMCredentialRequest(BaseModel):
    model: str | None = Field(default=None, max_length=200)


class LLMCredentialTestResponse(BaseModel):
    ok: bool
    credential_id: str
    model: str
    message: str
    response_preview: str


class AssistantLLMRequest(BaseModel):
    """Vazio = segue a credencial padrao e o modelo padrao dela (RN-40)."""

    credential_id: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=200)


class AssistantLLMResponse(BaseModel):
    credential_id: str | None
    model: str | None
    effective_credential_id: str | None
    effective_credential_name: str | None
    effective_provider: str
    effective_model: str
    source: str
    model_falls_back: bool


class AssistantRetrievalRequest(BaseModel):
    """Substitui o perfil inteiro; campo nulo volta ao padrao (RF-91)."""

    hybrid_enabled: StrictBool | None = None
    candidates: StrictInt | None = None
    top_k: StrictInt | None = None
    min_score: float | None = None


class RetrievalFieldResponse(BaseModel):
    stored: bool | int | float | None
    effective: bool | int | float
    origin: str


class RetrievalLimitsResponse(BaseModel):
    """D6, para a tela validar antes de enviar."""

    candidates: tuple[int, int]
    top_k: tuple[int, int]
    min_score: tuple[float, float]


class AssistantRetrievalResponse(BaseModel):
    hybrid_enabled: RetrievalFieldResponse
    candidates: RetrievalFieldResponse
    top_k: RetrievalFieldResponse
    min_score: RetrievalFieldResponse
    top_k_clamped: bool
    limits: RetrievalLimitsResponse
