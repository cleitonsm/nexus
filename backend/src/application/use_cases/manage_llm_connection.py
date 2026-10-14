from __future__ import annotations

from dataclasses import dataclass

from src.application.services import AccessControl
from src.domain import (
    AuditAction,
    AuditResource,
    AuthenticatedUser,
    LLMConnection,
    LLMConnectionRepository,
)

SOURCE_STORED = "configurado"
SOURCE_ENVIRONMENT = "ambiente"


def resolve_llm_connection(
    repository: LLMConnectionRepository,
    default: LLMConnection,
) -> LLMConnection:
    """RF-70: o valor gravado pela tela vence o do ambiente (D2)."""
    return repository.get() or default


@dataclass(frozen=True, slots=True)
class LLMConnectionDTO:
    provider: str
    model: str
    api_url: str
    source: str

    @classmethod
    def from_connection(cls, connection: LLMConnection, *, stored: bool) -> LLMConnectionDTO:
        return cls(
            provider=connection.provider.value,
            model=connection.model,
            api_url=connection.api_url,
            source=SOURCE_STORED if stored else SOURCE_ENVIRONMENT,
        )


class GetLLMConnectionUseCase:
    """RF-68: configuracao efetiva e de onde ela vem."""

    def __init__(
        self,
        *,
        repository: LLMConnectionRepository,
        access_control: AccessControl,
        default: LLMConnection,
    ) -> None:
        self._repository = repository
        self._access = access_control
        self._default = default

    def execute(self, user: AuthenticatedUser) -> LLMConnectionDTO:
        self._access.require_llm_configuration(user, AuditAction.LLM_SETTINGS_CHANGED)
        stored = self._repository.get()
        return LLMConnectionDTO.from_connection(
            stored or self._default, stored=stored is not None
        )


@dataclass(frozen=True, slots=True)
class UpdateLLMConnectionInput:
    user: AuthenticatedUser
    provider: str
    model: str
    api_url: str | None = None


class UpdateLLMConnectionUseCase:
    """RF-69 e RF-71: so o administrador altera; a troca vai para a auditoria."""

    def __init__(
        self,
        *,
        repository: LLMConnectionRepository,
        access_control: AccessControl,
        default: LLMConnection,
        allow_insecure_http: bool = False,
    ) -> None:
        self._repository = repository
        self._access = access_control
        self._default = default
        self._allow_insecure_http = allow_insecure_http

    def execute(self, data: UpdateLLMConnectionInput) -> LLMConnectionDTO:
        self._access.require_llm_configuration(
            data.user, AuditAction.LLM_SETTINGS_CHANGED
        )
        connection = LLMConnection.build(
            provider=data.provider,
            model=data.model,
            api_url=data.api_url,
            allow_insecure_http=self._allow_insecure_http,
        )
        previous = self._repository.get() or self._default
        saved = self._repository.save(connection, updated_by=data.user.id)
        self._access.audit(
            data.user,
            AuditAction.LLM_SETTINGS_CHANGED,
            resource_type=AuditResource.SETTINGS,
            details={
                "provider": saved.provider.value,
                "model": saved.model,
                "api_url": saved.api_url,
                "previous_provider": previous.provider.value,
                "previous_model": previous.model,
                "previous_api_url": previous.api_url,
            },
        )
        return LLMConnectionDTO.from_connection(saved, stored=True)
