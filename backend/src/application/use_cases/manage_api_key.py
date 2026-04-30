from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.domain import SecretSettingsRepository

GLOBAL_LLM_API_KEY = "global_llm_api_key"


class SecretCipher(Protocol):
    def encrypt(self, plaintext: str) -> str: ...

    def decrypt(self, ciphertext: str) -> str: ...


@dataclass(frozen=True, slots=True)
class SaveGlobalApiKeyInput:
    api_key: str


@dataclass(frozen=True, slots=True)
class ApiKeyStatusResult:
    configured: bool


class SaveGlobalApiKeyUseCase:
    def __init__(
        self,
        *,
        secret_repository: SecretSettingsRepository,
        secret_cipher: SecretCipher,
    ) -> None:
        self._secret_repository = secret_repository
        self._secret_cipher = secret_cipher

    def execute(self, data: SaveGlobalApiKeyInput) -> ApiKeyStatusResult:
        api_key = data.api_key.strip()
        if not api_key:
            raise ValueError("api_key must not be empty.")
        encrypted_value = self._secret_cipher.encrypt(api_key)
        self._secret_repository.set_encrypted_value(
            key_name=GLOBAL_LLM_API_KEY,
            encrypted_value=encrypted_value,
        )
        return ApiKeyStatusResult(configured=True)


class GetGlobalApiKeyStatusUseCase:
    def __init__(self, *, secret_repository: SecretSettingsRepository) -> None:
        self._secret_repository = secret_repository

    def execute(self) -> ApiKeyStatusResult:
        encrypted_value = self._secret_repository.get_encrypted_value(
            key_name=GLOBAL_LLM_API_KEY
        )
        return ApiKeyStatusResult(configured=bool(encrypted_value))


class GetGlobalApiKeyValueUseCase:
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
