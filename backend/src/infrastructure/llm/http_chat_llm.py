from __future__ import annotations

import json
from urllib import error, request

from src.domain import ChatMessage, LLMGateway


class LLMConfigurationError(ValueError):
    pass


class LLMProviderError(RuntimeError):
    pass


class HttpChatCompletionsLLM(LLMGateway):
    def __init__(
        self,
        *,
        api_url: str,
        model: str,
        api_key: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_url.strip():
            raise LLMConfigurationError("LLM_API_URL must not be empty.")
        if not model.strip():
            raise LLMConfigurationError("LLM_MODEL must not be empty.")
        if not api_key.strip():
            raise LLMConfigurationError("Global LLM API key is not configured.")
        self._api_url = api_url
        self._model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def generate(
        self,
        *,
        prompt: str,
        context_chunks: list[str],
        conversation_history: list[ChatMessage],
    ) -> str:
        context_text = "\n\n".join(
            chunk.strip() for chunk in context_chunks if chunk.strip()
        )
        system_text = (
            "Voce e um assistente de suporte do Nexus. Responda em portugues, de forma objetiva, "
            "e use apenas o contexto recuperado quando ele existir."
        )
        if context_text:
            system_text = f"{system_text}\n\nContexto recuperado:\n{context_text}"

        messages: list[dict[str, str]] = [{"role": "system", "content": system_text}]
        for item in conversation_history:
            messages.append({"role": item.role.value, "content": item.content})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
        }
        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            url=self._api_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self._timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            raise LLMProviderError(
                f"LLM provider rejected request: {exc.code} {details}"
            ) from exc
        except error.URLError as exc:
            raise LLMProviderError("LLM provider is unreachable.") from exc

        try:
            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMProviderError("LLM provider returned an invalid response payload.") from exc
        return str(content).strip()
