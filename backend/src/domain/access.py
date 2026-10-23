"""Identidade e regras de acesso (SPEC-004, RN-20 a RN-24).

Nada aqui depende de framework, de biblioteca de JWT ou do Keycloak: o token
e validado atras da porta ``TokenVerifier`` e chega ao dominio ja como
``AuthenticatedUser``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from .errors import DomainValidationError

MAX_GROUP_NAME_LENGTH = 255


class Role(StrEnum):
    """Papeis de realm do Keycloak reconhecidos pelo Nexus (RF-41)."""

    ADMIN = "nexus-admin"
    CURATOR = "nexus-curador"
    USER = "nexus-usuario"


def normalize_group(name: str) -> str:
    """Nome de grupo como o Nexus o compara: sem espacos e sem a barra inicial.

    O Keycloak publica o grupo ``rh`` como ``/rh`` quando o mapeador usa o
    caminho completo; os dois formatos designam o mesmo grupo.
    """
    normalized = name.strip().lstrip("/").strip()
    if not normalized:
        raise DomainValidationError("group name must not be empty.")
    if len(normalized) > MAX_GROUP_NAME_LENGTH:
        raise DomainValidationError(
            f"group name must be at most {MAX_GROUP_NAME_LENGTH} characters."
        )
    return normalized


def normalize_groups(names: Iterable[str]) -> frozenset[str]:
    return frozenset(normalize_group(name) for name in names)


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """Quem faz a requisicao, conforme o token validado (RN-20)."""

    id: str
    name: str = ""
    roles: frozenset[Role] = frozenset()
    groups: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        user_id = self.id.strip()
        if not user_id:
            raise DomainValidationError("user id must not be empty.")
        object.__setattr__(self, "id", user_id)
        object.__setattr__(self, "name", self.name.strip() or user_id)
        object.__setattr__(self, "roles", frozenset(Role(r) for r in self.roles))
        object.__setattr__(self, "groups", normalize_groups(self.groups))

    @property
    def is_admin(self) -> bool:
        return Role.ADMIN in self.roles

    @property
    def is_curator(self) -> bool:
        return Role.CURATOR in self.roles

    @property
    def has_role(self) -> bool:
        """Token sem nenhum papel do Nexus nao da acesso a funcionalidade alguma."""
        return bool(self.roles)


class AccessPolicy:
    """Decisoes de acesso; todas negam por padrao (RN-21 a RN-24).

    ``assistant_groups`` sao os grupos vinculados ao assistente e
    ``document_groups`` os grupos a que um documento esta restrito (vazio
    quando o documento segue o acesso do assistente).
    """

    @staticmethod
    def can_access_assistant(
        user: AuthenticatedUser,
        assistant_groups: frozenset[str],
    ) -> bool:
        """RN-22: assistente sem grupo e visivel apenas a administradores."""
        if user.is_admin:
            return True
        return user.has_role and bool(user.groups & assistant_groups)

    @staticmethod
    def can_manage_assistants(user: AuthenticatedUser) -> bool:
        """RN-21: assistentes e permissoes sao do administrador."""
        return user.is_admin

    @staticmethod
    def can_manage_documents(
        user: AuthenticatedUser,
        assistant_groups: frozenset[str],
    ) -> bool:
        """RN-21: o curador gerencia documentos dos assistentes a que tem acesso."""
        if user.is_admin:
            return True
        return user.is_curator and bool(user.groups & assistant_groups)

    @staticmethod
    def can_configure_llm(user: AuthenticatedUser) -> bool:
        return user.is_admin

    @staticmethod
    def can_view_audit(user: AuthenticatedUser) -> bool:
        return user.is_admin

    @staticmethod
    def owns_conversation(
        user: AuthenticatedUser,
        owner_user_id: str | None,
    ) -> bool:
        """RN-24: so quem criou a conversa a le; nem o administrador.

        Conversa sem dono (anterior a autenticacao) nao pertence a ninguem.
        """
        return owner_user_id is not None and owner_user_id == user.id

    @staticmethod
    def document_matches_groups(
        user_groups: frozenset[str],
        document_groups: frozenset[str],
    ) -> bool:
        """Regra do filtro aplicado na busca: sem restricao, ou grupo em comum."""
        return not document_groups or bool(user_groups & document_groups)

    @classmethod
    def can_read_document(
        cls,
        user: AuthenticatedUser,
        assistant_groups: frozenset[str],
        document_groups: frozenset[str],
    ) -> bool:
        """RN-23: a restricao do documento so restringe; nunca amplia.

        Pertencer a um grupo do documento nao dispensa o acesso ao assistente,
        e a restricao vale tambem para administradores fora do grupo.
        """
        return cls.can_access_assistant(
            user, assistant_groups
        ) and cls.document_matches_groups(user.groups, document_groups)
