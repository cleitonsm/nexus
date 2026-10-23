"""Grupos informados contra a lista do Keycloak (SPEC-009, RF-74)."""

from __future__ import annotations

import logging

from src.domain import (
    DomainValidationError,
    GroupDirectory,
    GroupDirectoryUnavailableError,
    normalize_group,
)

logger = logging.getLogger(__name__)


class UnknownGroupsError(DomainValidationError):
    """Algum grupo informado nao existe no Keycloak (D3): ninguem o teria."""

    def __init__(self, groups: list[str]) -> None:
        self.groups = groups
        super().__init__(
            "unknown groups (not found in Keycloak): " + ", ".join(groups) + "."
        )


def ensure_known_groups(
    groups: frozenset[str],
    directory: GroupDirectory | None,
) -> None:
    """Recusa grupos que o Keycloak nao conhece; ``groups`` ja vem normalizado.

    Sem grupos (remover a restricao) ou sem diretorio nao ha o que validar. Se o
    Keycloak nao responde, a validacao e ignorada e registrada (D3): a lista e
    uma protecao contra erro de digitacao, nao uma regra de seguranca.
    """
    if not groups or directory is None:
        return
    try:
        names = directory.list_groups()
    except GroupDirectoryUnavailableError:
        logger.warning(
            "groups.validation.skipped",
            extra={"reason": "directory_unavailable", "group_count": len(groups)},
        )
        return
    known: set[str] = set()
    for name in names:
        try:
            known.add(normalize_group(name))
        except DomainValidationError:
            continue
    unknown = sorted(group for group in groups if group not in known)
    if unknown:
        raise UnknownGroupsError(unknown)
