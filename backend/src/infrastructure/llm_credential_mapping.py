"""Conversao entre as colunas JSON da SPEC-013 e o dominio, sem SQLAlchemy.

Fica separada dos repositorios para ser testada sem banco. Registro invalido
nunca derruba a leitura: a credencial e ignorada e o perfil volta vazio, com
aviso no log (o chat segue a resolucao da RN-40 e da RN-41).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from src.domain import (
    DomainValidationError,
    LLMCredential,
    LLMCredentialId,
    LLMModelOption,
    LLMProvider,
    RetrievalProfile,
)

logger = logging.getLogger(__name__)


def models_to_json(models: Sequence[LLMModelOption]) -> list[dict[str, Any]]:
    """Precos como texto, para o JSON nao perder casas decimais."""
    return [
        {
            "name": option.name,
            "input_per_1k": _price_to_json(option.input_per_1k),
            "output_per_1k": _price_to_json(option.output_per_1k),
        }
        for option in models
    ]


def models_from_json(raw: object) -> tuple[LLMModelOption, ...]:
    if not isinstance(raw, list):
        raise DomainValidationError("stored models must be a list.")
    options: list[LLMModelOption] = []
    for item in raw:
        if not isinstance(item, Mapping) or "name" not in item:
            raise DomainValidationError("stored model must have a name.")
        options.append(
            LLMModelOption(
                name=str(item["name"]),
                input_per_1k=_price_from_json(item.get("input_per_1k")),
                output_per_1k=_price_from_json(item.get("output_per_1k")),
            )
        )
    return tuple(options)


def credential_from_row(
    *,
    credential_id: str,
    name: str,
    provider: str,
    api_url: str,
    models: object,
    default_model: str,
    is_default: bool,
    encrypted_key: str | None,
) -> LLMCredential | None:
    """``None`` quando o registro nao passa nas regras do dominio (RN-39)."""
    try:
        return LLMCredential(
            id=LLMCredentialId(credential_id),
            name=name,
            provider=LLMProvider(provider),
            api_url=api_url,
            models=models_from_json(models),
            default_model=default_model,
            is_default=bool(is_default),
            key_configured=bool(encrypted_key),
        )
    except (DomainValidationError, ValueError):
        logger.warning(
            "llm_credential.invalid_stored_value",
            extra={"credential_id": credential_id},
        )
        return None


def profile_from_json(raw: object, *, assistant_id: str) -> RetrievalProfile:
    if raw is None:
        return RetrievalProfile()
    try:
        if not isinstance(raw, Mapping):
            raise DomainValidationError("stored retrieval profile must be an object.")
        return RetrievalProfile.from_dict(raw)
    except DomainValidationError:
        logger.warning(
            "assistant.invalid_retrieval_profile",
            extra={"assistant_id": assistant_id},
        )
        return RetrievalProfile()


def profile_to_json(profile: RetrievalProfile) -> dict[str, Any] | None:
    stored = profile.as_dict()
    return stored or None


def _price_to_json(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _price_from_json(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise DomainValidationError("stored model price is not a number.") from exc
