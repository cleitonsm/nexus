"""Credenciais de LLM (SPEC-013, RN-37 a RN-40).

Uma credencial reune provedor, URL, os modelos permitidos (D4) com preco
opcional (D8) e o indicador de chave configurada. A chave em si nunca passa
pelo dominio (RN-39): o repositorio guarda so o ciphertext.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from urllib.parse import urlsplit

from .entities import Assistant
from .errors import DomainValidationError, LLMCredentialInUseError
from .llm_settings import (
    PROVIDER_ENDPOINTS,
    LLMConnection,
    LLMProvider,
    validate_model_name,
)
from .usage import LLMPricing
from .value_objects import AssistantId, LLMCredentialId

# Dependencia de mao unica: este modulo conhece ``Assistant`` (RN-38), entao
# ``entities`` nunca deve importar daqui; o assistente guarda so o id.

MAX_CREDENTIAL_NAME_LENGTH = 100


@dataclass(frozen=True, slots=True)
class LLMModelOption:
    """Modelo permitido na credencial; preco de entrada e saida juntos (T1)."""

    name: str
    input_per_1k: Decimal | None = None
    output_per_1k: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", validate_model_name(self.name))
        prices = (self.input_per_1k, self.output_per_1k)
        if (prices[0] is None) != (prices[1] is None):
            raise DomainValidationError(
                "model price needs both input_per_1k and output_per_1k."
            )
        if any(price is not None and price < 0 for price in prices):
            raise DomainValidationError("model prices must not be negative.")

    @property
    def has_price(self) -> bool:
        return self.input_per_1k is not None

    def pricing(self, currency: str) -> LLMPricing | None:
        """Preco do modelo; ``None`` quando o consumo deve usar o ambiente."""
        if self.input_per_1k is None or self.output_per_1k is None:
            return None
        return LLMPricing(
            input_per_1k=self.input_per_1k,
            output_per_1k=self.output_per_1k,
            currency=currency,
        )


@dataclass(frozen=True, slots=True)
class LLMCredential:
    id: LLMCredentialId
    name: str
    provider: LLMProvider
    api_url: str
    models: tuple[LLMModelOption, ...]
    default_model: str
    is_default: bool = False
    key_configured: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _validated_name(self.name))
        object.__setattr__(self, "models", tuple(self.models))
        _ensure_safe_url(self.provider, self.api_url)
        if not self.models:
            raise DomainValidationError("credential needs at least one model.")
        names = [option.name for option in self.models]
        if len(set(names)) != len(names):
            raise DomainValidationError("credential models must not repeat.")
        default_model = self.default_model.strip()
        if default_model not in names:
            raise DomainValidationError("default_model must be one of the models.")
        object.__setattr__(self, "default_model", default_model)

    @classmethod
    def build(
        cls,
        *,
        credential_id: str,
        name: str,
        provider: str,
        api_url: str | None,
        models: Sequence[LLMModelOption],
        default_model: str,
        is_default: bool = False,
        key_configured: bool = False,
        allow_insecure_http: bool = False,
    ) -> LLMCredential:
        """Valida o que o administrador informou (D5; URL pelas regras da SPEC-008)."""
        connection = LLMConnection.build(
            provider=provider,
            model=default_model,
            api_url=api_url,
            allow_insecure_http=allow_insecure_http,
        )
        return cls(
            id=LLMCredentialId(credential_id),
            name=name,
            provider=connection.provider,
            api_url=connection.api_url,
            models=tuple(models),
            default_model=default_model,
            is_default=is_default,
            key_configured=key_configured,
        )

    @property
    def model_names(self) -> tuple[str, ...]:
        return tuple(option.name for option in self.models)

    def model(self, name: str | None) -> LLMModelOption:
        """Modelo pedido; ``None`` e o padrao da credencial (RN-40)."""
        wanted = self.default_model if name is None else name.strip()
        for option in self.models:
            if option.name == wanted:
                return option
        raise DomainValidationError(f"model '{wanted}' is not allowed by the credential.")

    def model_with_fallback(self, name: str | None) -> tuple[LLMModelOption, bool]:
        """D11: para quem segue a padrao, modelo ausente recua ao padrao.

        Devolve o modelo usado e se houve recuo; quem escolheu a credencial
        usa ``model``, porque a RN-38 garante que o modelo continua na lista.
        """
        if name is not None and name.strip() not in self.model_names:
            return self.model(None), True
        return self.model(name), False

    def connection_for(self, model_name: str | None = None) -> LLMConnection:
        """Destino da chamada no formato que o cliente HTTP ja usa."""
        return LLMConnection(
            provider=self.provider,
            model=self.model(model_name).name,
            api_url=self.api_url,
        )

    def with_default(self, is_default: bool) -> LLMCredential:
        return replace(self, is_default=is_default)

    def with_key_configured(self, key_configured: bool) -> LLMCredential:
        return replace(self, key_configured=key_configured)


def default_for_new(existing: Iterable[LLMCredential], *, requested: bool) -> bool:
    """RN-37: a primeira credencial cadastrada ja nasce padrao."""
    return requested or not any(True for _ in existing)


def default_after_change(
    credentials: Iterable[LLMCredential], chosen: LLMCredentialId
) -> tuple[LLMCredential, ...]:
    """RN-37: marcar uma como padrao desmarca as outras."""
    items = tuple(credentials)
    if not any(item.id == chosen for item in items):
        raise DomainValidationError("credential to mark as default does not exist.")
    return tuple(item.with_default(item.id == chosen) for item in items)


def ensure_single_default(credentials: Iterable[LLMCredential]) -> None:
    items = tuple(credentials)
    defaults = sum(1 for item in items if item.is_default)
    if items and defaults != 1:
        raise DomainValidationError(
            "exactly one credential must be the default when any exists."
        )


def assistants_using(
    credential_id: LLMCredentialId, assistants: Iterable[Assistant]
) -> tuple[AssistantId, ...]:
    """Assistentes que escolheram a credencial (os sem escolha seguem a padrao)."""
    return tuple(
        item.id for item in assistants if item.llm_credential_id == credential_id
    )


def assistants_following_default(
    assistants: Iterable[Assistant],
) -> tuple[AssistantId, ...]:
    """Assistentes sem credencial propria: mudam junto com a padrao (RN-40)."""
    return tuple(item.id for item in assistants if item.llm_credential_id is None)


def assistants_falling_back(
    default: LLMCredential, assistants: Iterable[Assistant]
) -> tuple[AssistantId, ...]:
    """D11: seguidores da padrao cujo modelo ela nao tem (a tela avisa)."""
    return tuple(
        item.id
        for item in assistants
        if item.llm_credential_id is None
        and item.llm_model is not None
        and item.llm_model not in default.model_names
    )


def ensure_removable(
    credential: LLMCredential, assistants: Iterable[Assistant]
) -> None:
    """RN-38: a padrao e a escolhida por algum assistente nao saem.

    Para a padrao, a lista traz tambem os assistentes que a seguem.
    """
    items = tuple(assistants)
    users = tuple(item.value for item in assistants_using(credential.id, items))
    if credential.is_default:
        followers = tuple(item.value for item in assistants_following_default(items))
        raise LLMCredentialInUseError(
            "the default credential cannot be removed.",
            assistant_ids=users + followers,
            is_default=True,
        )
    if users:
        raise LLMCredentialInUseError(
            "the credential is used by assistants.", assistant_ids=users
        )


def ensure_models_removable(
    current: LLMCredential,
    updated: LLMCredential,
    assistants: Iterable[Assistant],
) -> None:
    """RN-38: modelo escolhido por algum assistente nao sai da lista.

    Vale para quem escolheu a credencial; quem segue a padrao tem recuo (D11).
    O erro junta todos os modelos removidos em uso e todos os assistentes.
    """
    removed = set(current.model_names) - set(updated.model_names)
    if not removed:
        return
    blocked = tuple(
        item
        for item in assistants
        if item.llm_credential_id == current.id and item.llm_model in removed
    )
    if not blocked:
        return
    models = tuple(
        model
        for model in current.model_names
        if any(item.llm_model == model for item in blocked)
    )
    raise LLMCredentialInUseError(
        f"models in use by assistants: {', '.join(models)}.",
        assistant_ids=tuple(item.id.value for item in blocked),
        models=models,
    )


def _ensure_safe_url(provider: LLMProvider, api_url: str) -> None:
    """RN-39 em qualquer construcao (tela, repositorio, migracao).

    O esquema (https ou http local) fica com ``build``; aqui so o que poderia
    carregar segredo: usuario/senha, parametros de consulta e fragmento.
    """
    value = api_url.strip()
    if not value:
        raise DomainValidationError("api_url must not be empty.")
    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise DomainValidationError("api_url is not a valid URL.") from exc
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise DomainValidationError("api_url must not contain credentials.")
    if parts.query or parts.fragment:
        raise DomainValidationError(
            "api_url must not contain query parameters or a fragment."
        )
    preset = PROVIDER_ENDPOINTS.get(provider)
    if preset is not None and value != preset:
        raise DomainValidationError("api_url must be the provider endpoint.")


def _validated_name(name: str) -> str:
    value = name.strip()
    if not value:
        raise DomainValidationError("credential name must not be empty.")
    if len(value) > MAX_CREDENTIAL_NAME_LENGTH:
        raise DomainValidationError(
            f"credential name must have at most {MAX_CREDENTIAL_NAME_LENGTH} characters."
        )
    if any(ord(char) < 32 for char in value):
        raise DomainValidationError("credential name must not contain control characters.")
    return value
