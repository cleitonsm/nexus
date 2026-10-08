"""PC-D6: grupos do Keycloak para escolher em vez de digitar."""

from __future__ import annotations

from src.application.services import AccessControl
from src.domain import AuthenticatedUser, GroupDirectory


class ListAvailableGroupsUseCase:
    """Administrador e curador consultam; a lista nao entra na auditoria.

    Sem o diretorio (Keycloak fora do ar ou cliente nao configurado), levanta
    ``GroupDirectoryUnavailableError`` e a tela volta ao campo de texto.
    """

    def __init__(self, directory: GroupDirectory, access_control: AccessControl) -> None:
        self._directory = directory
        self._access = access_control

    def execute(self, user: AuthenticatedUser) -> list[str]:
        self._access.require_group_listing(user)
        names = {name.strip() for name in self._directory.list_groups()}
        return sorted((name for name in names if name), key=str.casefold)
