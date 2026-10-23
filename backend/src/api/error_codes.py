"""Codigos estaveis de erro da API (fix-14).

O corpo de erro mantem ``detail`` e ganha ``code``; o frontend continua lendo
``detail`` e passa a poder decidir pelo ``code``. Sem dependencia do FastAPI.
"""

from __future__ import annotations

_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
    429: "usage_limit",
    500: "internal_error",
    502: "upstream_error",
    503: "unavailable",
}


def error_code(status_code: int) -> str:
    """Codigo do status; status sem entrada usa a familia (``client_error``...)."""
    if status_code in _CODES:
        return _CODES[status_code]
    return "client_error" if 400 <= status_code < 500 else "server_error"


def error_body(status_code: int, detail: object) -> dict[str, object]:
    """``{detail, code}``; o ``code`` do proprio ``detail`` (objeto) tem prioridade.

    O ``detail`` nunca e achatado: quem le ``body["detail"]["document_id"]``
    (409 de duplicado, RN-26) continua lendo igual.
    """
    if isinstance(detail, dict) and isinstance(detail.get("code"), str):
        return {"detail": detail, "code": detail["code"]}
    return {"detail": detail, "code": error_code(status_code)}
