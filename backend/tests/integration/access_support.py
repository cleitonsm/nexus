"""Apoio dos testes de integracao da SPEC-004: identidade e acesso em memoria.

Os testes de integracao sao descobertos a partir de ``tests/integration``,
por isso estes dubles nao sao importados de ``tests/unit``.
"""

from __future__ import annotations

from fastapi import FastAPI

from src.api.dependencies import (
    get_access_control,
    get_current_user,
    get_token_verifier,
)
from src.api.errors import register_error_handlers
from src.application.services import AccessControl, AuditTrail
from src.domain import (
    AssistantId,
    AuditEvent,
    AuditQuery,
    AuthenticatedUser,
    AuthenticationError,
    DocumentId,
    Role,
)

ADMIN = AuthenticatedUser(id="admin-1", name="Admin", roles=frozenset({Role.ADMIN}))


def member(user_id: str, *groups: str, role: Role = Role.USER) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user_id,
        name=user_id,
        roles=frozenset({role}),
        groups=frozenset(groups),
    )


class InMemoryPermissionRepository:
    def __init__(self) -> None:
        self.assistant_groups: dict[str, frozenset[str]] = {}
        self.document_groups: dict[str, frozenset[str]] = {}

    def get_assistant_groups(self, assistant_id: AssistantId) -> frozenset[str]:
        return self.assistant_groups.get(assistant_id.value, frozenset())

    def list_assistant_groups(self) -> dict[str, frozenset[str]]:
        return {key: value for key, value in self.assistant_groups.items() if value}

    def set_assistant_groups(
        self, assistant_id: AssistantId, groups: frozenset[str]
    ) -> None:
        self.assistant_groups[assistant_id.value] = frozenset(groups)

    def get_document_groups(self, document_id: DocumentId) -> frozenset[str]:
        return self.document_groups.get(document_id.value, frozenset())

    def list_document_groups(
        self, assistant_id: AssistantId
    ) -> dict[str, frozenset[str]]:
        return {key: value for key, value in self.document_groups.items() if value}

    def set_document_groups(
        self, document_id: DocumentId, groups: frozenset[str]
    ) -> None:
        self.document_groups[document_id.value] = frozenset(groups)


class InMemoryAuditLog:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event

    def list_events(self, query: AuditQuery) -> list[AuditEvent]:
        matching = [
            event
            for event in reversed(self.events)
            if (query.user_id is None or event.user_id == query.user_id)
            and (query.action is None or event.action == query.action)
            and (
                query.assistant_id is None
                or event.details.get("assistant_id") == query.assistant_id
            )
        ]
        return matching[query.offset : query.offset + query.limit]

    def actions(self) -> list[str]:
        return [event.action for event in self.events]


class StaticTokenVerifier:
    """``TokenVerifier`` dublado: cada token conhecido e um usuario."""

    def __init__(self, users: dict[str, AuthenticatedUser]) -> None:
        self._users = users

    def verify(self, token: str) -> AuthenticatedUser:
        try:
            return self._users[token]
        except KeyError as exc:
            raise AuthenticationError("invalid token.") from exc


class AccessHarness:
    """Liga a um app de teste a identidade e o controle de acesso em memoria."""

    def __init__(self, app: FastAPI, user: AuthenticatedUser = ADMIN) -> None:
        self.app = app
        self.user = user
        self.permissions = InMemoryPermissionRepository()
        self.audit = InMemoryAuditLog()
        self.control = AccessControl(
            permission_repository=self.permissions,
            audit_trail=AuditTrail(self.audit),
        )
        register_error_handlers(app)
        app.dependency_overrides[get_access_control] = lambda: self.control
        app.dependency_overrides[get_current_user] = lambda: self.user

    def use_tokens(self, users: dict[str, AuthenticatedUser]) -> None:
        """Volta a exigir o cabecalho de autorizacao, validado pelo duble."""
        self.app.dependency_overrides.pop(get_current_user, None)
        self.app.dependency_overrides[get_token_verifier] = lambda: (
            StaticTokenVerifier(users)
        )

    def link_assistant(self, assistant_id: str, *groups: str) -> None:
        self.permissions.set_assistant_groups(
            AssistantId(assistant_id), frozenset(groups)
        )


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TokenFactory:
    """Emite tokens RS256 como os do Keycloak, com uma chave gerada no teste."""

    ISSUER = "http://keycloak.test/realms/nexus"
    AUDIENCE = "nexus-api"
    KID = "test-key"

    def __init__(self) -> None:
        from cryptography.hazmat.primitives.asymmetric import rsa

        self._private = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def jwks(self) -> dict[str, object]:
        numbers = self._private.public_key().public_numbers()
        size = (numbers.n.bit_length() + 7) // 8
        return {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": self.KID,
                    "n": _b64(numbers.n.to_bytes(size, "big")),
                    "e": _b64(numbers.e.to_bytes(3, "big")),
                }
            ]
        }

    def verifier(self):
        from src.infrastructure.auth import KeycloakTokenVerifier

        return KeycloakTokenVerifier(
            issuer=self.ISSUER,
            audience=self.AUDIENCE,
            jwks_fetcher=self.jwks,
        )

    def token(
        self,
        subject: str,
        *,
        roles: tuple[str, ...] = (),
        groups: tuple[str, ...] = (),
        **overrides: object,
    ) -> str:
        import json
        import time

        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        claims: dict[str, object] = {
            "iss": self.ISSUER,
            "aud": [self.AUDIENCE],
            "sub": subject,
            "exp": time.time() + 300,
            "preferred_username": subject,
            "realm_access": {"roles": list(roles)},
            "groups": list(groups),
        }
        claims.update(overrides)
        header = {"alg": "RS256", "typ": "JWT", "kid": self.KID}
        signing_input = ".".join(
            _b64(json.dumps(part).encode("utf-8")) for part in (header, claims)
        )
        signature = self._private.sign(
            signing_input.encode("ascii"), padding.PKCS1v15(), hashes.SHA256()
        )
        return f"{signing_input}.{_b64(signature)}"


def _b64(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")
