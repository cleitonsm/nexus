from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.application.services import AccessControl
from src.domain import (
    AuditAction,
    AuditResource,
    AuthenticatedUser,
    SecretSettingsRepository,
)

GLOBAL_LLM_API_KEY = "global_llm_api_key"


class SecretCipher(Protocol):
    def encrypt(self, plaintext: str) -> str: ...

    def decrypt(self, ciphertext: str) -> str: ...


@dataclass(frozen=True, slots=True)
class SaveGlobalApiKeyInput:
    user: AuthenticatedUser
    api_key: str


@dataclass(frozen=True, slots=True)
class ApiKeyStatusResult:
    configured: bool


class SaveGlobalApiKeyUseCase:
    """RF-47: so o administrador troca a chave; a troca fica na auditoria."""

    def __init__(
        self,
        *,
        secret_repository: SecretSettingsRepository,
        secret_cipher: SecretCipher,
        access_control: AccessControl,
    ) -> None:
        self._secret_repository = secret_repository
        self._secret_cipher = secret_cipher
        self._access = access_control

    def execute(self, data: SaveGlobalApiKeyInput) -> ApiKeyStatusResult:
        self._access.require_llm_configuration(
            data.user, AuditAction.LLM_API_KEY_CHANGED
        )
        api_key = data.api_key.strip()
        if not api_key:
            raise ValueError("api_key must not be empty.")
        encrypted_value = self._secret_cipher.encrypt(api_key)
        self._secret_repository.set_encrypted_value(
            key_name=GLOBAL_LLM_API_KEY,
            encrypted_value=encrypted_value,
        )
        self._access.audit(
            data.user,
            AuditAction.LLM_API_KEY_CHANGED,
            resource_type=AuditResource.SETTINGS,
            resource_id=GLOBAL_LLM_API_KEY,
        )
        return ApiKeyStatusResult(configured=True)


class GetGlobalApiKeyStatusUseCase:
    def __init__(
        self,
        *,
        secret_repository: SecretSettingsRepository,
        access_control: AccessControl,
    ) -> None:
        self._secret_repository = secret_repository
        self._access = access_control

    def execute(self, user: AuthenticatedUser) -> ApiKeyStatusResult:
        self._access.require_llm_configuration(user, AuditAction.LLM_API_KEY_CHANGED)
        encrypted_value = self._secret_repository.get_encrypted_value(
            key_name=GLOBAL_LLM_API_KEY
        )
        return ApiKeyStatusResult(configured=bool(encrypted_value))


class GetGlobalApiKeyValueUseCase:
    """Uso interno, na chamada ao LLM; nunca exposto por rota."""

    def __init__(
        self,
        *,
        secret_repository: SecretSettingsRepository,
        secret_cipher: SecretCipher,
    ) -> None:
        self._secret_repository = secret_repository
        self._secret_cipher = secret_cipher

    def execute(self) -> str | None:
        encrypted_value = self._secret_repository.get_encrypted_value(
            key_name=GLOBAL_LLM_API_KEY
        )
        if not encrypted_value:
            return None
        return self._secret_cipher.decrypt(encrypted_value)
