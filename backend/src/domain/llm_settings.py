"""Conexao com o LLM definida na tela de administracao (SPEC-008).

Provedor, modelo e URL do endpoint compativel com a API de chat completions da
OpenAI. A chave fica a parte (ADR 0005) e nunca passa por aqui.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from .errors import DomainValidationError

MAX_MODEL_LENGTH = 200
MAX_URL_LENGTH = 2048


class LLMProvider(StrEnum):
    OPENAI = "openai"
    GEMINI = "gemini"
    CUSTOM = "custom"


# D7: presets com URL fixa; so ``CUSTOM`` aceita URL digitada.
PROVIDER_ENDPOINTS: dict[LLMProvider, str] = {
    LLMProvider.OPENAI: "https://api.openai.com/v1/chat/completions",
    LLMProvider.GEMINI: (
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    ),
}


def provider_for_url(api_url: str) -> LLMProvider:
    """Provedor cuja URL padrao e ``api_url``; qualquer outra e ``CUSTOM``."""
    normalized = api_url.strip()
    for provider, endpoint in PROVIDER_ENDPOINTS.items():
        if normalized == endpoint:
            return provider
    return LLMProvider.CUSTOM


@dataclass(frozen=True, slots=True)
class LLMConnection:
    provider: LLMProvider
    model: str
    api_url: str

    @classmethod
    def from_environment(cls, *, model: str, api_url: str) -> LLMConnection:
        """Padrao do ambiente: sem as regras de entrada do usuario (D2)."""
        return cls(
            provider=provider_for_url(api_url),
            model=model.strip(),
            api_url=api_url.strip(),
        )

    @classmethod
    def build(
        cls,
        *,
        provider: str,
        model: str,
        api_url: str | None,
        allow_insecure_http: bool = False,
    ) -> LLMConnection:
        """Valida o que o administrador informou (RF-69, D1, D3)."""
        try:
            chosen = LLMProvider(provider)
        except ValueError as exc:
            raise DomainValidationError(
                f"provider must be one of: {', '.join(item.value for item in LLMProvider)}."
            ) from exc
        clean_model = _validated_model(model)
        if chosen is LLMProvider.CUSTOM:
            url = _validated_url(api_url or "", allow_insecure_http)
        else:
            # O preset vale mesmo que o cliente envie outra URL (CT-67).
            url = PROVIDER_ENDPOINTS[chosen]
        return cls(provider=chosen, model=clean_model, api_url=url)


def _validated_model(model: str) -> str:
    value = model.strip()
    if not value:
        raise DomainValidationError("model must not be empty.")
    if len(value) > MAX_MODEL_LENGTH:
        raise DomainValidationError(
            f"model must have at most {MAX_MODEL_LENGTH} characters."
        )
    if any(char.isspace() or ord(char) < 32 for char in value):
        raise DomainValidationError("model must not contain spaces or control characters.")
    return value


def _validated_url(raw: str, allow_insecure_http: bool) -> str:
    value = raw.strip()
    if not value:
        raise DomainValidationError("api_url is required for the custom provider.")
    if len(value) > MAX_URL_LENGTH:
        raise DomainValidationError(f"api_url must have at most {MAX_URL_LENGTH} characters.")
    if any(char.isspace() or ord(char) < 32 for char in value):
        raise DomainValidationError("api_url must not contain spaces or control characters.")
    try:
        parts = urlsplit(value)
        hostname = parts.hostname
        parts.port  # noqa: B018 - levanta ValueError se a porta for invalida
    except ValueError as exc:
        raise DomainValidationError("api_url is not a valid URL.") from exc
    allowed = {"https", "http"} if allow_insecure_http else {"https"}
    if parts.scheme not in allowed:
        raise DomainValidationError(
            "api_url must use https."
            if not allow_insecure_http
            else "api_url must use http or https."
        )
    if not hostname:
        raise DomainValidationError("api_url must have a host.")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise DomainValidationError("api_url must not contain credentials.")
    if parts.query or parts.fragment:
        raise DomainValidationError(
            "api_url must not contain query parameters or a fragment."
        )
    return value
