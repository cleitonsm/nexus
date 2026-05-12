from __future__ import annotations

import json
from pathlib import Path
import time
from urllib import error, request
from urllib.parse import urlparse
from uuid import uuid4

from src.domain import ChatMessage, LLMGateway


class LLMConfigurationError(ValueError):
    pass


class LLMProviderError(RuntimeError):
    pass


def _agent_debug_log(
    *,
    run_id: str,
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict[str, object],
) -> None:
    payload = {
        "sessionId": "8fd7a3",
        "id": f"log_{int(time.time() * 1000)}_{uuid4().hex[:8]}",
        "timestamp": int(time.time() * 1000),
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
    }
    try:
        with Path("debug-8fd7a3.log").open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except OSError:
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
            raise LLMConfigurationError(
                "Global LLM API key is not configured."
            )
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
            "Voce e um assistente de suporte do Nexus. "
            "Responda em portugues, de forma objetiva, "
            "e use apenas o contexto recuperado quando ele existir."
        )
        if context_text:
            system_text = (
                f"{system_text}\n\nContexto recuperado:\n{context_text}"
            )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_text}
        ]
        for item in conversation_history:
            messages.append({"role": item.role.value, "content": item.content})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
        }
        body = json.dumps(payload).encode("utf-8")
        # region agent log
        _agent_debug_log(
            run_id="pre-fix",
            hypothesis_id="H3,H5",
            location="backend/src/infrastructure/llm/http_chat_llm.py:generate:start",
            message="Calling LLM API",
            data={"url": self._api_url, "model": self._model},
        )
        # endregion
        parsed_url = urlparse(self._api_url)
        # region agent log
        _agent_debug_log(
            run_id="llm-ui-pre-fix",
            hypothesis_id="H7,H9",
            location="backend/src/infrastructure/llm/http_chat_llm.py:start",
            message="starting llm provider request",
            data={
                "apiHost": parsed_url.netloc,
                "apiPath": parsed_url.path,
                "model": self._model,
                "messageCount": len(messages),
                "contextChunks": len(context_chunks),
                "bodySizeBytes": len(body),
            },
        )
        # endregion
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
            with request.urlopen(
                http_request,
                timeout=self._timeout_seconds,
            ) as response:
                status_code = response.status
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            # region agent log
            _agent_debug_log(
                run_id="llm-ui-pre-fix",
                hypothesis_id="H7,H9",
                location=(
                    "backend/src/infrastructure/llm/"
                    "http_chat_llm.py:http_error"
                ),
                message="llm provider rejected request",
                data={
                    "statusCode": exc.code,
                    "detailLength": len(details),
                    "model": self._model,
                },
            )
            # endregion
            raise LLMProviderError(
                f"LLM provider rejected request: {exc.code} {details}"
            ) from exc
        except error.URLError as exc:
            # region agent log
            _agent_debug_log(
                run_id="llm-ui-pre-fix",
                hypothesis_id="H7,H9",
                location=(
                    "backend/src/infrastructure/llm/"
                    "http_chat_llm.py:url_error"
                ),
                message="llm provider unreachable",
                data={"reason": str(exc.reason), "model": self._model},
            )
            # endregion
            raise LLMProviderError("LLM provider is unreachable.") from exc

        try:
            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            # region agent log
            _agent_debug_log(
                run_id="llm-ui-pre-fix",
                hypothesis_id="H9",
                location=(
                    "backend/src/infrastructure/llm/"
                    "http_chat_llm.py:invalid_response"
                ),
                message="llm provider returned invalid response",
                data={"statusCode": status_code, "rawLength": len(raw)},
            )
            # endregion
            raise LLMProviderError(
                "LLM provider returned an invalid response payload."
            ) from exc
        # region agent log
        _agent_debug_log(
            run_id="llm-ui-pre-fix",
            hypothesis_id="H9",
            location="backend/src/infrastructure/llm/http_chat_llm.py:success",
            message="llm provider returned content",
            data={
                "statusCode": status_code,
                "contentLength": len(str(content)),
            },
        )
        # endregion
        return str(content).strip()
