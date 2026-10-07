from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import TextIO
from uuid import uuid4

_request_id: ContextVar[str | None] = ContextVar("nexus_request_id", default=None)

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SENSITIVE_FIELD = re.compile(
    r"api_?key|secret|authorization|password|credential|(^|_)token$",
    re.IGNORECASE,
)
_MAX_VALUE_LENGTH = 300
_STANDARD_ATTRIBUTES = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", (), None))
) | {"message", "asctime", "taskName"}
_HANDLER_NAME = "nexus-json"
# O servidor HTTP instala handlers proprios em texto puro. Seus loggers passam
# a propagar para o raiz; o de acesso e silenciado porque o middleware ja
# registra `http.request.finished` com o identificador da requisicao.
_SERVER_LOGGERS = ("uvicorn", "uvicorn.error")
_SILENCED_LOGGERS = ("uvicorn.access",)


def get_request_id() -> str | None:
    return _request_id.get()


def bind_request_id(request_id: str) -> Token[str | None]:
    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)


def normalize_request_id(incoming: str | None) -> str:
    """Aceita o identificador recebido apenas se for seguro para o log."""
    if incoming and _SAFE_REQUEST_ID.fullmatch(incoming):
        return incoming
    return uuid4().hex


class JsonLogFormatter(logging.Formatter):
    """Uma linha JSON por evento, sem segredos e com valores truncados."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": get_request_id(),
            "event": record.getMessage(),
        }
        for name, value in vars(record).items():
            if name not in _STANDARD_ATTRIBUTES and not name.startswith("_"):
                payload[name] = _sanitize(name, value)
        if record.exc_info and record.exc_info[1] is not None:
            payload["error_type"] = type(record.exc_info[1]).__name__
            payload["error"] = _truncate(str(record.exc_info[1]))
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(
    *,
    level: str = "INFO",
    stream: TextIO | None = None,
) -> None:
    """Instala o formato JSON no logger raiz; chamadas repetidas sao seguras."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if handler.get_name() == _HANDLER_NAME:
            root.removeHandler(handler)
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(JsonLogFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())
    _adopt_server_loggers()


def _adopt_server_loggers() -> None:
    for name in _SERVER_LOGGERS:
        server_logger = logging.getLogger(name)
        server_logger.handlers.clear()
        server_logger.propagate = True
    for name in _SILENCED_LOGGERS:
        silenced = logging.getLogger(name)
        silenced.handlers.clear()
        silenced.propagate = False


def _sanitize(name: str, value: object) -> object:
    if _SENSITIVE_FIELD.search(name):
        return "[redacted]"
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    return _truncate(str(value))


def _truncate(text: str) -> str:
    if len(text) <= _MAX_VALUE_LENGTH:
        return text
    return text[:_MAX_VALUE_LENGTH] + "..."
