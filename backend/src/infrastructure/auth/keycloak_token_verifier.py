"""Validacao do token de acesso emitido pelo Keycloak (RNF-22).

A assinatura RS256 e conferida com ``cryptography``, que o projeto ja usa:
nenhuma biblioteca de JWT foi acrescentada. So RS256 e aceito; qualquer outro
algoritmo declarado no cabecalho, inclusive ``none``, e recusado.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import threading
import time
from collections.abc import Callable
from urllib import error, request

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from src.domain import AuthenticatedUser, AuthenticationError, Role

ACCEPTED_ALGORITHM = "RS256"
DEFAULT_JWKS_CACHE_SECONDS = 300.0
# Intervalo minimo entre consultas provocadas por um ``kid`` desconhecido:
# tokens forjados nao podem transformar a API em carga sobre o Keycloak.
DEFAULT_JWKS_MIN_REFRESH_SECONDS = 10.0
DEFAULT_TIMEOUT_SECONDS = 5.0
_KNOWN_ROLES = {role.value for role in Role}

logger = logging.getLogger(__name__)

JwksFetcher = Callable[[], dict[str, object]]


def issuer_url(keycloak_url: str, realm: str) -> str:
    return f"{keycloak_url.rstrip('/')}/realms/{realm}"


def http_jwks_fetcher(
    jwks_url: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> JwksFetcher:
    def fetch() -> dict[str, object]:
        with request.urlopen(jwks_url, timeout=timeout_seconds) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))

    return fetch


class KeycloakTokenVerifier:
    """Confere assinatura (JWKS), emissor, audiencia e validade do token."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_fetcher: JwksFetcher,
        clock: Callable[[], float] = time.time,
        jwks_cache_seconds: float = DEFAULT_JWKS_CACHE_SECONDS,
        jwks_min_refresh_seconds: float = DEFAULT_JWKS_MIN_REFRESH_SECONDS,
    ) -> None:
        if not issuer.strip() or not audience.strip():
            raise ValueError("issuer and audience must not be empty.")
        self._issuer = issuer.strip()
        self._audience = audience.strip()
        self._fetch_jwks = jwks_fetcher
        self._clock = clock
        self._cache_seconds = jwks_cache_seconds
        self._min_refresh_seconds = jwks_min_refresh_seconds
        self._keys: dict[str, rsa.RSAPublicKey] = {}
        self._fetched_at: float | None = None
        self._lock = threading.Lock()

    def verify(self, token: str) -> AuthenticatedUser:
        header, claims, signing_input, signature = _split(token)
        if header.get("alg") != ACCEPTED_ALGORITHM:
            raise AuthenticationError("unsupported token algorithm.")
        key = self._key(header.get("kid"))
        try:
            key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
        except InvalidSignature as exc:
            raise AuthenticationError("invalid token signature.") from exc
        self._check_claims(claims)
        return _to_user(claims)

    def _check_claims(self, claims: dict[str, object]) -> None:
        now = self._clock()
        if claims.get("iss") != self._issuer:
            raise AuthenticationError("unexpected token issuer.")
        audience = claims.get("aud")
        audiences = audience if isinstance(audience, list) else [audience]
        if self._audience not in audiences:
            raise AuthenticationError("unexpected token audience.")
        expires_at = claims.get("exp")
        if not _is_number(expires_at) or now >= float(expires_at):  # type: ignore[arg-type]
            raise AuthenticationError("token expired.")
        not_before = claims.get("nbf")
        if _is_number(not_before) and now < float(not_before):  # type: ignore[arg-type]
            raise AuthenticationError("token not valid yet.")

    def _key(self, kid: object) -> rsa.RSAPublicKey:
        if not isinstance(kid, str) or not kid:
            raise AuthenticationError("token without key id.")
        with self._lock:
            now = self._clock()
            if self._should_refresh(kid, now):
                self._refresh(now)
            key = self._keys.get(kid)
        if key is None:
            raise AuthenticationError("unknown token signing key.")
        return key

    def _should_refresh(self, kid: str, now: float) -> bool:
        if self._fetched_at is None:
            return True
        age = now - self._fetched_at
        if age >= self._cache_seconds:
            return True
        # Chave nova apos rotacao no Keycloak: busca de novo, com intervalo.
        return kid not in self._keys and age >= self._min_refresh_seconds

    def _refresh(self, now: float) -> None:
        try:
            document = self._fetch_jwks()
        except (error.URLError, OSError, ValueError) as exc:
            logger.warning("auth.jwks.unavailable", exc_info=exc)
            if self._fetched_at is None:
                raise AuthenticationError(
                    "identity provider keys are unavailable."
                ) from exc
            # Com chaves ja conhecidas, uma falha passageira nao derruba o login.
            self._fetched_at = now
            return
        self._keys = _parse_jwks(document)
        self._fetched_at = now


def _split(token: str) -> tuple[dict[str, object], dict[str, object], bytes, bytes]:
    parts = token.strip().split(".")
    if len(parts) != 3 or not all(parts):
        raise AuthenticationError("malformed token.")
    try:
        header = json.loads(_b64decode(parts[0]))
        claims = json.loads(_b64decode(parts[1]))
        signature = _b64decode(parts[2])
    except (ValueError, binascii.Error) as exc:
        raise AuthenticationError("malformed token.") from exc
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise AuthenticationError("malformed token.")
    return header, claims, f"{parts[0]}.{parts[1]}".encode("ascii"), signature


def _b64decode(segment: str) -> bytes:
    padded = segment + "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _parse_jwks(document: dict[str, object]) -> dict[str, rsa.RSAPublicKey]:
    keys: dict[str, rsa.RSAPublicKey] = {}
    entries = document.get("keys")
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        if entry.get("kty") != "RSA" or entry.get("use", "sig") != "sig":
            continue
        kid, modulus, exponent = entry.get("kid"), entry.get("n"), entry.get("e")
        if not all(isinstance(item, str) and item for item in (kid, modulus, exponent)):
            continue
        try:
            numbers = rsa.RSAPublicNumbers(
                e=int.from_bytes(_b64decode(str(exponent)), "big"),
                n=int.from_bytes(_b64decode(str(modulus)), "big"),
            )
            keys[str(kid)] = numbers.public_key()
        except (ValueError, binascii.Error):
            continue
    return keys


def _to_user(claims: dict[str, object]) -> AuthenticatedUser:
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise AuthenticationError("token without subject.")
    name = claims.get("name") or claims.get("preferred_username") or subject
    return AuthenticatedUser(
        id=subject,
        name=str(name),
        roles=frozenset(Role(role) for role in _realm_roles(claims)),
        groups=frozenset(_groups(claims)),
    )


def _realm_roles(claims: dict[str, object]) -> list[str]:
    realm_access = claims.get("realm_access")
    roles = realm_access.get("roles") if isinstance(realm_access, dict) else None
    return [
        role
        for role in (roles if isinstance(roles, list) else [])
        if isinstance(role, str) and role in _KNOWN_ROLES
    ]


def _groups(claims: dict[str, object]) -> list[str]:
    groups = claims.get("groups")
    return [
        group
        for group in (groups if isinstance(groups, list) else [])
        if isinstance(group, str) and group.strip().strip("/")
    ]
