"""Credenciais de LLM na administracao (SPEC-013, RF-87 a RF-89, RF-94).

So o administrador consulta e altera (D7). A chave entra em texto, e cifrada
aqui e nunca volta: os DTOs trazem apenas ``key_configured`` (RN-39). Toda
alteracao vai para a auditoria com o antes e o depois, sem a chave.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import uuid4

from src.application.services import AccessControl
from src.domain import (
    Assistant,
    AssistantRepository,
    AuditAction,
    AuditResource,
    AuthenticatedUser,
    DomainValidationError,
    LLMConnection,
    LLMCredential,
    LLMCredentialId,
    LLMCredentialRepository,
    LLMGateway,
    LLMModelOption,
    SecretCipher,
    assistants_falling_back,
    assistants_following_default,
    assistants_using,
    default_for_new,
    ensure_models_removable,
    ensure_removable,
)

LLMGatewayFactory = Callable[[LLMConnection, str], LLMGateway]
# Leituras negadas ficam na auditoria como leitura, nao como alteracao.
LIST_ATTEMPT = "llm_credential.listed"
IMPACT_ATTEMPT = "llm_credential.impact_viewed"
TEST_PROMPT = "Teste de conectividade do Nexus. Responda apenas: OK"


class LLMCredentialNotFoundError(LookupError):
    """A credencial informada nao existe."""


class LLMCredentialKeyMissingError(RuntimeError):
    """A credencial nao tem chave gravada (servico nao configurado)."""


# --- DTOs -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LLMModelDTO:
    name: str
    input_per_1k: Decimal | None
    output_per_1k: Decimal | None


@dataclass(frozen=True, slots=True)
class LLMCredentialDTO:
    id: str
    name: str
    provider: str
    api_url: str
    models: tuple[LLMModelDTO, ...]
    default_model: str
    is_default: bool
    key_configured: bool
    # Assistentes que escolheram esta credencial.
    assistant_ids: tuple[str, ...] = ()
    # So na padrao: assistentes que a seguem sem escolha propria.
    following_assistant_ids: tuple[str, ...] = ()

    @classmethod
    def from_credential(
        cls,
        credential: LLMCredential,
        *,
        assistant_ids: Sequence[str] = (),
        following_assistant_ids: Sequence[str] = (),
    ) -> LLMCredentialDTO:
        return cls(
            id=credential.id.value,
            name=credential.name,
            provider=credential.provider.value,
            api_url=credential.api_url,
            models=tuple(
                LLMModelDTO(
                    name=option.name,
                    input_per_1k=option.input_per_1k,
                    output_per_1k=option.output_per_1k,
                )
                for option in credential.models
            ),
            default_model=credential.default_model,
            is_default=credential.is_default,
            key_configured=credential.key_configured,
            assistant_ids=tuple(assistant_ids),
            following_assistant_ids=tuple(following_assistant_ids),
        )


@dataclass(frozen=True, slots=True)
class LLMCredentialOptionDTO:
    """Para o formulario do assistente: sem URL nem estado da chave."""

    id: str
    name: str
    provider: str
    models: tuple[str, ...]
    default_model: str
    is_default: bool


@dataclass(frozen=True, slots=True)
class DefaultChangeImpactDTO:
    """D11: o que acontece se a credencial virar padrao (ou mudar de modelos)."""

    credential_id: str
    following_assistant_ids: tuple[str, ...]
    falling_back_assistant_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LLMCredentialTestDTO:
    ok: bool
    credential_id: str
    model: str
    response_preview: str


# --- Entradas ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LLMModelInput:
    name: str
    input_per_1k: Decimal | None = None
    output_per_1k: Decimal | None = None

    def to_option(self) -> LLMModelOption:
        return LLMModelOption(
            name=self.name,
            input_per_1k=self.input_per_1k,
            output_per_1k=self.output_per_1k,
        )


@dataclass(frozen=True, slots=True)
class CreateLLMCredentialInput:
    user: AuthenticatedUser
    name: str
    provider: str
    models: tuple[LLMModelInput, ...]
    default_model: str
    # RN-39: nunca em repr, log ou traceback.
    api_key: str = field(repr=False)
    api_url: str | None = None
    make_default: bool = False


@dataclass(frozen=True, slots=True)
class UpdateLLMCredentialInput:
    user: AuthenticatedUser
    credential_id: str
    name: str
    provider: str
    models: tuple[LLMModelInput, ...]
    default_model: str
    api_url: str | None = None
    # Preenchida = rotacao da chave; vazia = mantem a gravada. Nunca em repr.
    api_key: str | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class LLMCredentialRefInput:
    user: AuthenticatedUser
    credential_id: str


@dataclass(frozen=True, slots=True)
class DefaultChangeImpactInput:
    user: AuthenticatedUser
    credential_id: str
    # Simula uma lista de modelos diferente da gravada (edicao em curso).
    model_names: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class TestLLMCredentialInput:
    user: AuthenticatedUser
    credential_id: str
    model: str | None = None


# --- Base comum -------------------------------------------------------------


class _CredentialUseCase:
    def __init__(
        self,
        *,
        credentials: LLMCredentialRepository,
        assistants: AssistantRepository,
        access_control: AccessControl,
    ) -> None:
        self._credentials = credentials
        self._assistants = assistants
        self._access = access_control

    def _require_admin(self, user: AuthenticatedUser, action: AuditAction | str) -> None:
        self._access.require_llm_configuration(user, action)

    def _get(self, credential_id: str) -> LLMCredential:
        credential = self._credentials.get(LLMCredentialId(credential_id))
        if credential is None:
            raise LLMCredentialNotFoundError("credential not found.")
        return credential

    def _followers(self, credential: LLMCredential, assistants: Sequence[Assistant]) -> list[str]:
        if not credential.is_default:
            return []
        return [item.value for item in assistants_following_default(assistants)]

    def _ensure_unique_name(self, name: str, *, except_id: str | None = None) -> None:
        wanted = name.strip().casefold()
        for item in self._credentials.list_all():
            if item.id.value != except_id and item.name.casefold() == wanted:
                raise DomainValidationError("credential name is already in use.")

    def _audit(
        self,
        user: AuthenticatedUser,
        action: AuditAction,
        credential_id: str,
        details: dict[str, object],
    ) -> None:
        self._access.audit(
            user,
            action,
            resource_type=AuditResource.SETTINGS,
            resource_id=credential_id,
            details={"credential_id": credential_id, **details},
        )


def _snapshot(credential: LLMCredential) -> dict[str, object]:
    """O que a auditoria guarda da credencial; nunca a chave (RN-39)."""
    return {
        "name": credential.name,
        "provider": credential.provider.value,
        "api_url": credential.api_url,
        "models": list(credential.model_names),
        "priced_models": [
            option.name for option in credential.models if option.has_price
        ],
        "default_model": credential.default_model,
        "is_default": credential.is_default,
    }


def _clean_key(api_key: str | None) -> str | None:
    value = (api_key or "").strip()
    return value or None


# --- Casos de uso -----------------------------------------------------------


class ListLLMCredentialsUseCase(_CredentialUseCase):
    """RF-87: lista com quem usa cada credencial."""

    def execute(self, user: AuthenticatedUser) -> list[LLMCredentialDTO]:
        self._require_admin(user, LIST_ATTEMPT)
        assistants = self._assistants.list_all()
        followers = tuple(
            item.value for item in assistants_following_default(assistants)
        )
        return [
            LLMCredentialDTO.from_credential(
                credential,
                assistant_ids=[
                    item.value for item in assistants_using(credential.id, assistants)
                ],
                following_assistant_ids=followers if credential.is_default else (),
            )
            for credential in self._credentials.list_all()
        ]


class ListLLMCredentialOptionsUseCase(_CredentialUseCase):
    """Opcoes do formulario do assistente; so quem escolhe o LLM (D7) consulta."""

    def execute(self, user: AuthenticatedUser) -> list[LLMCredentialOptionDTO]:
        self._require_admin(user, LIST_ATTEMPT)
        return [
            LLMCredentialOptionDTO(
                id=item.id.value,
                name=item.name,
                provider=item.provider.value,
                models=item.model_names,
                default_model=item.default_model,
                is_default=item.is_default,
            )
            for item in self._credentials.list_all()
        ]


class CreateLLMCredentialUseCase(_CredentialUseCase):
    """RF-87 e RN-37: a primeira credencial nasce padrao."""

    def __init__(
        self,
        *,
        credentials: LLMCredentialRepository,
        assistants: AssistantRepository,
        access_control: AccessControl,
        cipher: SecretCipher,
        allow_insecure_http: bool = False,
        id_factory: Callable[[], str] = lambda: uuid4().hex,
    ) -> None:
        super().__init__(
            credentials=credentials, assistants=assistants, access_control=access_control
        )
        self._cipher = cipher
        self._allow_insecure_http = allow_insecure_http
        self._id_factory = id_factory

    def execute(self, data: CreateLLMCredentialInput) -> LLMCredentialDTO:
        self._require_admin(data.user, AuditAction.LLM_CREDENTIAL_CREATED)
        api_key = _clean_key(data.api_key)
        if api_key is None:
            raise DomainValidationError("api_key must not be empty.")
        existing = self._credentials.list_all()
        previous_default = next((item for item in existing if item.is_default), None)
        credential = LLMCredential.build(
            credential_id=self._id_factory(),
            name=data.name,
            provider=data.provider,
            api_url=data.api_url,
            models=tuple(item.to_option() for item in data.models),
            default_model=data.default_model,
            is_default=default_for_new(existing, requested=data.make_default),
            allow_insecure_http=self._allow_insecure_http,
        )
        self._ensure_unique_name(credential.name)
        saved = self._credentials.save(
            credential,
            encrypted_key=self._cipher.encrypt(api_key),
            updated_by=data.user.id,
        )
        self._audit(
            data.user, AuditAction.LLM_CREDENTIAL_CREATED, saved.id.value, _snapshot(saved)
        )
        if saved.is_default and previous_default is not None:
            self._audit(
                data.user,
                AuditAction.LLM_CREDENTIAL_DEFAULT_CHANGED,
                saved.id.value,
                {"previous_default_id": previous_default.id.value},
            )
        return LLMCredentialDTO.from_credential(
            saved, following_assistant_ids=self._followers(saved, self._assistants.list_all())
        )


class UpdateLLMCredentialUseCase(_CredentialUseCase):
    """RF-87 e RN-38: modelo escolhido por algum assistente nao sai."""

    def __init__(
        self,
        *,
        credentials: LLMCredentialRepository,
        assistants: AssistantRepository,
        access_control: AccessControl,
        cipher: SecretCipher,
        allow_insecure_http: bool = False,
    ) -> None:
        super().__init__(
            credentials=credentials, assistants=assistants, access_control=access_control
        )
        self._cipher = cipher
        self._allow_insecure_http = allow_insecure_http

    def execute(self, data: UpdateLLMCredentialInput) -> LLMCredentialDTO:
        self._require_admin(data.user, AuditAction.LLM_CREDENTIAL_UPDATED)
        current = self._get(data.credential_id)
        updated = LLMCredential.build(
            credential_id=current.id.value,
            name=data.name,
            provider=data.provider,
            api_url=data.api_url,
            models=tuple(item.to_option() for item in data.models),
            default_model=data.default_model,
            is_default=current.is_default,
            key_configured=current.key_configured,
            allow_insecure_http=self._allow_insecure_http,
        )
        self._ensure_unique_name(updated.name, except_id=current.id.value)
        assistants = self._assistants.list_all()
        ensure_models_removable(current, updated, assistants)
        api_key = _clean_key(data.api_key)
        saved = self._credentials.save(
            updated,
            encrypted_key=self._cipher.encrypt(api_key) if api_key else None,
            updated_by=data.user.id,
        )
        previous = _snapshot(current)
        details: dict[str, object] = dict(_snapshot(saved))
        details.update({f"previous_{key}": value for key, value in previous.items()})
        if saved.is_default:
            details["falling_back_assistant_ids"] = [
                item.value for item in assistants_falling_back(saved, assistants)
            ]
        self._audit(data.user, AuditAction.LLM_CREDENTIAL_UPDATED, saved.id.value, details)
        if api_key:
            self._audit(data.user, AuditAction.LLM_CREDENTIAL_KEY_ROTATED, saved.id.value, {})
        return LLMCredentialDTO.from_credential(
            saved,
            assistant_ids=[item.value for item in assistants_using(saved.id, assistants)],
            following_assistant_ids=self._followers(saved, assistants),
        )


class DeleteLLMCredentialUseCase(_CredentialUseCase):
    """RN-38: a padrao e a escolhida por algum assistente nao saem."""

    def execute(self, data: LLMCredentialRefInput) -> None:
        self._require_admin(data.user, AuditAction.LLM_CREDENTIAL_DELETED)
        credential = self._get(data.credential_id)
        ensure_removable(credential, self._assistants.list_all())
        self._credentials.delete(credential.id)
        self._audit(
            data.user,
            AuditAction.LLM_CREDENTIAL_DELETED,
            credential.id.value,
            _snapshot(credential),
        )


class SetDefaultLLMCredentialUseCase(_CredentialUseCase):
    """RF-88 e RN-37: a anterior deixa de ser padrao na mesma transacao."""

    def execute(self, data: LLMCredentialRefInput) -> LLMCredentialDTO:
        self._require_admin(data.user, AuditAction.LLM_CREDENTIAL_DEFAULT_CHANGED)
        chosen = self._get(data.credential_id)
        previous = self._credentials.get_default()
        assistants = self._assistants.list_all()
        if previous is None or previous.id != chosen.id:
            self._credentials.set_default(chosen.id, updated_by=data.user.id)
            self._audit(
                data.user,
                AuditAction.LLM_CREDENTIAL_DEFAULT_CHANGED,
                chosen.id.value,
                {
                    "previous_default_id": previous.id.value if previous else None,
                    "following_assistant_ids": [
                        item.value for item in assistants_following_default(assistants)
                    ],
                    "falling_back_assistant_ids": [
                        item.value for item in assistants_falling_back(chosen, assistants)
                    ],
                },
            )
        saved = self._get(data.credential_id)
        return LLMCredentialDTO.from_credential(
            saved,
            assistant_ids=[item.value for item in assistants_using(saved.id, assistants)],
            following_assistant_ids=[
                item.value for item in assistants_following_default(assistants)
            ],
        )


class GetDefaultChangeImpactUseCase(_CredentialUseCase):
    """D11: antes de confirmar, quem segue a padrao e quem vai recuar."""

    def execute(self, data: DefaultChangeImpactInput) -> DefaultChangeImpactDTO:
        self._require_admin(data.user, IMPACT_ATTEMPT)
        candidate = self._get(data.credential_id)
        if data.model_names is not None:
            names = tuple(dict.fromkeys(name.strip() for name in data.model_names))
            if candidate.default_model not in names and names:
                default_model = names[0]
            else:
                default_model = candidate.default_model
            candidate = LLMCredential(
                id=candidate.id,
                name=candidate.name,
                provider=candidate.provider,
                api_url=candidate.api_url,
                models=tuple(LLMModelOption(name=name) for name in names),
                default_model=default_model,
            )
        assistants = self._assistants.list_all()
        return DefaultChangeImpactDTO(
            credential_id=candidate.id.value,
            following_assistant_ids=tuple(
                item.value for item in assistants_following_default(assistants)
            ),
            falling_back_assistant_ids=tuple(
                item.value for item in assistants_falling_back(candidate, assistants)
            ),
        )


class TestLLMCredentialUseCase(_CredentialUseCase):
    """RF-89: chama o provedor com um dos modelos da credencial."""

    def __init__(
        self,
        *,
        credentials: LLMCredentialRepository,
        assistants: AssistantRepository,
        access_control: AccessControl,
        cipher: SecretCipher,
        gateway_factory: LLMGatewayFactory,
    ) -> None:
        super().__init__(
            credentials=credentials, assistants=assistants, access_control=access_control
        )
        self._cipher = cipher
        self._gateway_factory = gateway_factory

    def execute(self, data: TestLLMCredentialInput) -> LLMCredentialTestDTO:
        self._require_admin(data.user, AuditAction.LLM_CREDENTIAL_TESTED)
        credential = self._get(data.credential_id)
        option = credential.model(data.model)
        encrypted = self._credentials.get_encrypted_key(credential.id)
        if not encrypted:
            raise LLMCredentialKeyMissingError("credential has no API key configured.")
        connection = credential.connection_for(option.name)
        self._audit(
            data.user,
            AuditAction.LLM_CREDENTIAL_TESTED,
            credential.id.value,
            {"llm_model": option.name, "llm_provider": credential.provider.value},
        )
        gateway = self._gateway_factory(connection, self._cipher.decrypt(encrypted))
        answer = gateway.generate(
            prompt=TEST_PROMPT, context_chunks=[], conversation_history=[]
        )
        return LLMCredentialTestDTO(
            ok=True,
            credential_id=credential.id.value,
            model=option.name,
            response_preview=answer[:200],
        )
