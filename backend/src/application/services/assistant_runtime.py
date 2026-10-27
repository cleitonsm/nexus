"""O que vale para uma pergunta a um assistente (SPEC-013, P4).

Reune a resolucao do LLM (RN-40, D8, D11) e a dos parametros de recuperacao
(RN-41) num so objeto, montado a cada pergunta. O chat, a avaliacao e a
calibracao usam o mesmo caminho, para medirem o que o usuario recebe.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from src.domain import (
    Assistant,
    LLMConnection,
    LLMCredentialRepository,
    LLMGateway,
    LLMPricing,
    ResolvedRetrievalProfile,
    RetrievalDefaults,
    SecretCipher,
)

from .llm_resolution import (
    ResolvedLLM,
    resolve_llm_for_assistant,
    resolve_retrieval_settings,
)
from .retrieval import RetrievalSettings

# Recebe o LLM resolvido (com a chave em memoria) e devolve o gateway da chamada.
LLMGatewayBuilder = Callable[[ResolvedLLM], LLMGateway]


@dataclass(frozen=True, slots=True)
class AssistantRuntime:
    retrieval: RetrievalSettings
    llm: ResolvedLLM
    llm_gateway: LLMGateway = field(repr=False)
    # RN-41: de onde veio cada parametro ("assistant" ou "default").
    retrieval_origins: Mapping[str, str] = field(default_factory=dict)
    top_k_clamped: bool = False

    @property
    def usage_model(self) -> str:
        return self.llm.connection.model

    @property
    def usage_pricing(self) -> LLMPricing | None:
        """``None``: o consumo usa os precos do ambiente (D8)."""
        return self.llm.pricing

    def log_fields(self) -> dict[str, object]:
        """Para log e span: nunca a chave (RN-39)."""
        return {
            "llm_source": self.llm.source.value,
            "llm_credential_id": self.llm.credential_id or "",
            "llm_provider": self.llm.connection.provider.value,
            "llm_model": self.llm.connection.model,
            "llm_model_fell_back": self.llm.model_fell_back,
            "has_llm_credential": bool(self.llm.api_key),
            "retrieval_hybrid": self.retrieval.hybrid_enabled,
            "retrieval_candidates": self.retrieval.candidates,
            "retrieval_top_n": self.retrieval.top_n,
            "retrieval_min_score": self.retrieval.min_score,
        }


AssistantRuntimeResolver = Callable[[Assistant], AssistantRuntime]


def retrieval_defaults(settings: RetrievalSettings) -> RetrievalDefaults:
    """O padrao global (ambiente) no formato do dominio."""
    return RetrievalDefaults(
        candidates=settings.candidates,
        top_k=settings.top_n,
        min_score=settings.min_score,
        hybrid_enabled=settings.hybrid_enabled,
    )


def assistant_retrieval_settings(
    assistant: Assistant, base_settings: RetrievalSettings
) -> RetrievalSettings:
    """RN-41: parametros do assistente sobre o padrao; orcamentos do ambiente."""
    profile = resolve_retrieval_settings(assistant, retrieval_defaults(base_settings))
    return _settings_from(profile, base_settings)


def _settings_from(
    profile: ResolvedRetrievalProfile, base_settings: RetrievalSettings
) -> RetrievalSettings:
    return RetrievalSettings(
        candidates=profile.candidates,
        top_n=profile.top_k,
        min_score=profile.min_score,
        context_token_budget=base_settings.context_token_budget,
        history_token_budget=base_settings.history_token_budget,
        structural_context_token_budget=base_settings.structural_context_token_budget,
        hybrid_enabled=profile.hybrid_enabled,
    )


def build_assistant_runtime(
    assistant: Assistant,
    *,
    base_settings: RetrievalSettings,
    credentials: LLMCredentialRepository,
    cipher: SecretCipher,
    environment: LLMConnection,
    currency: str,
    gateway_builder: LLMGatewayBuilder,
) -> AssistantRuntime:
    llm = resolve_llm_for_assistant(
        assistant,
        credentials=credentials,
        cipher=cipher,
        environment=environment,
        currency=currency,
    )
    profile = resolve_retrieval_settings(assistant, retrieval_defaults(base_settings))
    return AssistantRuntime(
        retrieval=_settings_from(profile, base_settings),
        llm=llm,
        llm_gateway=gateway_builder(llm),
        retrieval_origins={name: origin.value for name, origin in profile.origins.items()},
        top_k_clamped=profile.top_k_clamped,
    )
