"""Verificacao de segredos na partida (SPEC-007 fix-4).

Os valores padrao de ``.env.example`` existem so para o ambiente local. Fora
dele (``APP_ENV`` diferente de ``local``) a API e o worker nao iniciam com
eles. A mensagem cita o nome da variavel, nunca o valor.
"""

from __future__ import annotations

from collections.abc import Mapping

LOCAL_ENVIRONMENT = "local"

# Variavel -> valores padrao conhecidos (compose.yaml e .env.example).
DEFAULT_SECRETS: dict[str, frozenset[str]] = {
    "NEXUS_SECRETS_KEY": frozenset({"change-me-in-local-env"}),
    "QDRANT_API_KEY": frozenset({"nexus-local"}),
    "POSTGRES_PASSWORD": frozenset({"nexus"}),
    "KEYCLOAK_BACKEND_CLIENT_SECRET": frozenset({"nexus-backend-dev-secret"}),
}


class InsecureConfigurationError(RuntimeError):
    """Segredo ausente ou padrao fora do ambiente local."""


def is_local(env: Mapping[str, str]) -> bool:
    return env.get("APP_ENV", "").strip() == LOCAL_ENVIRONMENT


def check_deployment_secrets(env: Mapping[str, str]) -> list[str]:
    """Levanta ``InsecureConfigurationError`` se algum segredo for inseguro.

    Retorna lista vazia quando esta tudo certo (ou o ambiente e local).
    """
    if is_local(env):
        return []
    problems = [
        f"{name} is missing or still has the local default"
        for name, defaults in DEFAULT_SECRETS.items()
        if env.get(name, "").strip() in defaults | {""}
    ]
    if problems:
        raise InsecureConfigurationError(
            "refusing to start outside APP_ENV=local: " + "; ".join(problems) + "."
        )
    return []


def local_only_warning(env: Mapping[str, str]) -> str | None:
    """Aviso de que esta configuracao serve so para uso local."""
    if not is_local(env):
        return None
    return (
        "APP_ENV=local: portas publicadas apenas em 127.0.0.1, segredos padrao e "
        "usuarios de teste do Keycloak. Nao use esta configuracao fora do local."
    )
