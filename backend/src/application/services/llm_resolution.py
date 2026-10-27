"""Resolucao por pergunta do LLM e dos parametros de recuperacao (SPEC-013).

RN-40: credencial do assistente -> credencial padrao -> ambiente. O modelo e o
do assistente ou o padrao da credencial; quem segue a padrao e guardou um
modelo que ela nao tem recua ao modelo padrao dela (D11).

RN-41: parametros do assistente -> padrao global, campo a campo; nunca falha
na pergunta (T3).

A chave e decifrada so aqui, em memoria, para a chamada (RN-39); o resultado
nunca vai para log nem para a auditoria.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum

from src.domain import (
    Assistant,
    LLMConnection,
    LLMCredential,
    LLMCredentialRepository,
    LLMPricing,
    ResolvedRetrievalProfile,
    RetrievalDefaults,
    SecretCipher,
)

logger = logging.getLogger(__name__)


class LLMSource(StrEnum):
    ASSISTANT = "assistant"
    DEFAULT = "default"
    ENVIRONMENT = "environment"


@dataclass(frozen=True, slots=True)
class ResolvedLLM:
    connection: LLMConnection
    source: LLMSource
    credential_id: str | None = None
    credential_name: str | None = None
    # D11: o modelo guardado nao existe na padrao vigente.
    model_fell_back: bool = False
    # D8: ``None`` = o consumo usa ``LLM_PRICE_*``.
    pricing: LLMPricing | None = None
    # Nunca aparece em repr (RN-39).
    api_key: str | None = field(default=None, repr=False)


def resolve_llm_for_assistant(
    assistant: Assistant,
    *,
    credentials: LLMCredentialRepository,
    cipher: SecretCipher,
    environment: LLMConnection,
    currency: str,
) -> ResolvedLLM:
    if assistant.llm_credential_id is not None:
        chosen = credentials.get(assistant.llm_credential_id)
        if chosen is not None:
            return _from_credential(
                chosen,
                model=assistant.llm_model,
                assistant_id=assistant.id.value,
                source=LLMSource.ASSISTANT,
                credentials=credentials,
                cipher=cipher,
                currency=currency,
            )
        # A FK impede excluir a escolhida; isto so ocorre com registro invalido.
        logger.warning(
            "llm.resolution.credential_unavailable",
            extra={
                "assistant_id": assistant.id.value,
                "credential_id": assistant.llm_credential_id.value,
            },
        )
    return _default_or_environment(
        credentials=credentials,
        cipher=cipher,
        environment=environment,
        currency=currency,
        model=assistant.llm_model,
        assistant_id=assistant.id.value,
    )


def resolve_default_llm(
    *,
    credentials: LLMCredentialRepository,
    cipher: SecretCipher,
    environment: LLMConnection,
    currency: str,
) -> ResolvedLLM:
    """Fora de um assistente (sugestao de assistente): padrao -> ambiente."""
    return _default_or_environment(
        credentials=credentials,
        cipher=cipher,
        environment=environment,
        currency=currency,
        model=None,
        assistant_id=None,
    )


def _default_or_environment(
    *,
    credentials: LLMCredentialRepository,
    cipher: SecretCipher,
    environment: LLMConnection,
    currency: str,
    model: str | None,
    assistant_id: str | None,
) -> ResolvedLLM:
    default = credentials.get_default()
    if default is not None:
        return _from_credential(
            default,
            model=model,
            assistant_id=assistant_id,
            source=LLMSource.DEFAULT,
            credentials=credentials,
            cipher=cipher,
            currency=currency,
        )
    # Sem nenhuma credencial: comportamento de hoje sem chave (o chat decide).
    return ResolvedLLM(connection=environment, source=LLMSource.ENVIRONMENT)


def resolve_retrieval_settings(
    assistant: Assistant, defaults: RetrievalDefaults
) -> ResolvedRetrievalProfile:
    resolved = assistant.retrieval_profile.resolve(defaults)
    if resolved.top_k_clamped:
        logger.warning(
            "retrieval.top_k_clamped",
            extra={
                "assistant_id": assistant.id.value,
                "top_k": resolved.top_k,
                "candidates": resolved.candidates,
            },
        )
    return resolved


def _from_credential(
    credential: LLMCredential,
    *,
    model: str | None,
    assistant_id: str | None,
    source: LLMSource,
    credentials: LLMCredentialRepository,
    cipher: SecretCipher,
    currency: str,
) -> ResolvedLLM:
    option, fell_back = credential.model_with_fallback(model)
    if fell_back:
        logger.warning(
            "llm.resolution.model_fallback",
            extra={
                "assistant_id": assistant_id,
                "credential_id": credential.id.value,
                "requested_model": model,
                "used_model": option.name,
            },
        )
    encrypted = credentials.get_encrypted_key(credential.id)
    api_key: str | None = None
    if encrypted:
        try:
            api_key = cipher.decrypt(encrypted)
        except Exception:  # noqa: BLE001 - chave mestra trocada: segue sem chave
            # Erro do servidor, nao do cliente: o chat responde como "sem chave"
            # e o log aponta a credencial (nunca o ciphertext).
            logger.error(
                "llm.credential.decrypt_failed",
                extra={"credential_id": credential.id.value},
            )
    return ResolvedLLM(
        connection=credential.connection_for(option.name),
        source=source,
        credential_id=credential.id.value,
        credential_name=credential.name,
        model_fell_back=fell_back,
        pricing=option.pricing(currency),
        api_key=api_key,
    )
