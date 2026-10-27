"""Dubles da SPEC-013: credenciais, assistentes, cifra e LLM em memoria."""

from __future__ import annotations

from dataclasses import replace

from src.domain import (
    PROVIDER_ENDPOINTS,
    Assistant,
    AssistantId,
    AssistantName,
    LLMCredential,
    LLMCredentialId,
    LLMModelOption,
    LLMProvider,
)

# Chaves e ciphertexts ficticios.
FAKE_KEY = "sk-ficticia-123"


class PrefixCipher:
    """Cifra reversivel e obvia; o teste confere que o texto puro nunca e guardado."""

    def encrypt(self, plaintext: str) -> str:
        return f"enc:{plaintext[::-1]}"

    def decrypt(self, ciphertext: str) -> str:
        assert ciphertext.startswith("enc:"), "decifrando algo que nao foi cifrado"
        return ciphertext[4:][::-1]


class InMemoryCredentials:
    """Como o repositorio: guarda o ciphertext a parte e mantem uma padrao."""

    def __init__(self) -> None:
        self.items: dict[str, LLMCredential] = {}
        self.keys: dict[str, str] = {}
        self.saves: list[tuple[str, str | None, str]] = []

    def add(self, credential: LLMCredential, *, encrypted_key: str | None = None) -> None:
        self.save(credential, encrypted_key=encrypted_key, updated_by="seed")

    def list_all(self) -> list[LLMCredential]:
        return sorted(self.items.values(), key=lambda item: (not item.is_default, item.name))

    def get(self, credential_id: LLMCredentialId) -> LLMCredential | None:
        return self.items.get(credential_id.value)

    def get_default(self) -> LLMCredential | None:
        return next((item for item in self.items.values() if item.is_default), None)

    def get_encrypted_key(self, credential_id: LLMCredentialId) -> str | None:
        return self.keys.get(credential_id.value)

    def save(
        self,
        credential: LLMCredential,
        *,
        encrypted_key: str | None,
        updated_by: str,
    ) -> LLMCredential:
        if credential.is_default:
            self._clear_default(except_id=credential.id.value)
        if encrypted_key is not None:
            self.keys[credential.id.value] = encrypted_key
        stored = credential.with_key_configured(credential.id.value in self.keys)
        self.items[credential.id.value] = stored
        self.saves.append((credential.id.value, encrypted_key, updated_by))
        return stored

    def set_default(self, credential_id: LLMCredentialId, *, updated_by: str) -> None:
        if credential_id.value not in self.items:
            raise LookupError("credential not found.")
        self._clear_default(except_id=credential_id.value)
        self.items[credential_id.value] = self.items[credential_id.value].with_default(True)

    def delete(self, credential_id: LLMCredentialId) -> bool:
        self.keys.pop(credential_id.value, None)
        return self.items.pop(credential_id.value, None) is not None

    def _clear_default(self, *, except_id: str) -> None:
        for key, item in list(self.items.items()):
            if key != except_id and item.is_default:
                self.items[key] = item.with_default(False)


class InMemoryAssistants:
    def __init__(self, *assistants: Assistant) -> None:
        self.items = {item.id.value: item for item in assistants}

    def save(self, assistant: Assistant) -> Assistant:
        self.items[assistant.id.value] = assistant
        return assistant

    def list_all(self) -> list[Assistant]:
        return list(self.items.values())

    def get_by_id(self, assistant_id: AssistantId) -> Assistant | None:
        return self.items.get(assistant_id.value)

    def delete(self, assistant_id: AssistantId) -> bool:
        return self.items.pop(assistant_id.value, None) is not None

    def update(self, assistant_id: str, **changes: object) -> None:
        self.items[assistant_id] = replace(self.items[assistant_id], **changes)


class RecordingGateway:
    def __init__(self, answer: str = "OK", error: Exception | None = None) -> None:
        self.answer = answer
        self.error = error
        self.prompts: list[str] = []

    def generate(self, *, prompt: str, context_chunks: list, conversation_history: list) -> str:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.answer


def credential(
    credential_id: str,
    *,
    name: str | None = None,
    provider: LLMProvider = LLMProvider.OPENAI,
    models: tuple[str, ...] = ("gpt-4o-mini", "gpt-4o"),
    default_model: str | None = None,
    is_default: bool = False,
) -> LLMCredential:
    return LLMCredential(
        id=LLMCredentialId(credential_id),
        name=name or credential_id,
        provider=provider,
        api_url=PROVIDER_ENDPOINTS.get(provider, "https://llm.exemplo.com/v1/chat"),
        models=tuple(LLMModelOption(name=model) for model in models),
        default_model=default_model or models[0],
        is_default=is_default,
    )


def gemini(credential_id: str = "cred-gemini", **overrides: object) -> LLMCredential:
    values: dict[str, object] = {
        "name": "Gemini",
        "provider": LLMProvider.GEMINI,
        "models": ("gemini-3.8-flash", "gemini-3.8-pro"),
    }
    values.update(overrides)
    return credential(credential_id, **values)  # type: ignore[arg-type]


def assistant(
    assistant_id: str,
    *,
    credential_id: str | None = None,
    model: str | None = None,
) -> Assistant:
    return Assistant(
        id=AssistantId(assistant_id),
        name=AssistantName(f"Assistente {assistant_id}"),
        llm_credential_id=LLMCredentialId(credential_id) if credential_id else None,
        llm_model=model,
    )
