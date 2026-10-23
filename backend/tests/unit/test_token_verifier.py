"""SPEC-20261007-004, CT-23 (RNF-22): validacao do token, sem Keycloak."""

from __future__ import annotations

import base64
import json
import unittest

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from src.domain import AuthenticationError, Role
from src.infrastructure.auth import KeycloakTokenVerifier, issuer_url

ISSUER = "http://localhost:8080/realms/nexus"
AUDIENCE = "nexus-api"
NOW = 1_800_000_000.0


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _json(value: dict[str, object]) -> str:
    return _b64(json.dumps(value).encode("utf-8"))


class SigningKey:
    def __init__(self, kid: str) -> None:
        self.kid = kid
        self._private = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def jwk(self) -> dict[str, object]:
        numbers = self._private.public_key().public_numbers()
        return {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": self.kid,
            "n": _b64(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
            "e": _b64(numbers.e.to_bytes(3, "big")),
        }

    def sign(self, claims: dict[str, object], **header: object) -> str:
        head = {"alg": "RS256", "typ": "JWT", "kid": self.kid, **header}
        signing_input = f"{_json(head)}.{_json(claims)}"
        signature = self._private.sign(
            signing_input.encode("ascii"), padding.PKCS1v15(), hashes.SHA256()
        )
        return f"{signing_input}.{_b64(signature)}"


KEY = SigningKey("key-1")
OTHER_KEY = SigningKey("key-1")
ROTATED_KEY = SigningKey("key-2")


def _claims(**overrides: object) -> dict[str, object]:
    claims: dict[str, object] = {
        "iss": ISSUER,
        "aud": ["account", AUDIENCE],
        "sub": "3f0e5d0a-user",
        "exp": NOW + 300,
        "iat": NOW - 10,
        "name": "Ana Curadora",
        "preferred_username": "ana",
        "realm_access": {
            "roles": ["nexus-curador", "offline_access", "default-roles-nexus"]
        },
        "groups": ["/rh", "financeiro"],
    }
    claims.update(overrides)
    return {key: value for key, value in claims.items() if value is not None}


class Jwks:
    def __init__(self, *keys: SigningKey) -> None:
        self.keys = list(keys)
        self.calls = 0
        self.fail = False

    def __call__(self) -> dict[str, object]:
        self.calls += 1
        if self.fail:
            raise OSError("keycloak unreachable")
        return {"keys": [key.jwk() for key in self.keys]}


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> float:
        return self.now


class TokenVerifierTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.jwks = Jwks(KEY)
        self.clock = Clock()
        self.verifier = KeycloakTokenVerifier(
            issuer=ISSUER,
            audience=AUDIENCE,
            jwks_fetcher=self.jwks,
            clock=self.clock,
        )

    def _rejected(self, token: str) -> None:
        with self.assertRaises(AuthenticationError):
            self.verifier.verify(token)

    def test_valid_token_yields_user_roles_and_groups(self) -> None:
        user = self.verifier.verify(KEY.sign(_claims()))
        self.assertEqual(user.id, "3f0e5d0a-user")
        self.assertEqual(user.name, "Ana Curadora")
        self.assertEqual(user.roles, frozenset({Role.CURATOR}))
        self.assertEqual(user.groups, frozenset({"rh", "financeiro"}))

    def test_single_string_audience_is_accepted(self) -> None:
        user = self.verifier.verify(KEY.sign(_claims(aud=AUDIENCE)))
        self.assertEqual(user.id, "3f0e5d0a-user")

    def test_token_without_roles_or_groups_has_none(self) -> None:
        user = self.verifier.verify(
            KEY.sign(_claims(realm_access=None, groups=None, name=None))
        )
        self.assertEqual(user.roles, frozenset())
        self.assertEqual(user.groups, frozenset())
        self.assertEqual(user.name, "ana")

    def test_signature_from_another_key_is_rejected(self) -> None:
        self._rejected(OTHER_KEY.sign(_claims()))

    def test_tampered_claims_are_rejected(self) -> None:
        header, _, signature = KEY.sign(_claims()).split(".")
        forged = _json(_claims(realm_access={"roles": ["nexus-admin"]}))
        self._rejected(f"{header}.{forged}.{signature}")

    def test_wrong_issuer_is_rejected(self) -> None:
        self._rejected(KEY.sign(_claims(iss="http://evil.example/realms/nexus")))

    def test_wrong_audience_is_rejected(self) -> None:
        self._rejected(KEY.sign(_claims(aud=["account", "nexus-frontend"])))

    def test_missing_audience_is_rejected(self) -> None:
        self._rejected(KEY.sign(_claims(aud=None)))

    def test_expired_token_is_rejected(self) -> None:
        self._rejected(KEY.sign(_claims(exp=NOW - 1)))

    def test_token_expiring_now_is_rejected(self) -> None:
        self._rejected(KEY.sign(_claims(exp=NOW)))

    def test_token_without_expiration_is_rejected(self) -> None:
        self._rejected(KEY.sign(_claims(exp=None)))

    def test_token_not_valid_yet_is_rejected(self) -> None:
        self._rejected(KEY.sign(_claims(nbf=NOW + 60)))

    def test_token_without_subject_is_rejected(self) -> None:
        self._rejected(KEY.sign(_claims(sub=None)))

    def test_unsigned_token_is_rejected(self) -> None:
        unsigned = f"{_json({'alg': 'none', 'kid': 'key-1'})}.{_json(_claims())}."
        self._rejected(unsigned)
        self._rejected(unsigned + _b64(b"x"))

    def test_symmetric_algorithm_is_rejected(self) -> None:
        self._rejected(KEY.sign(_claims(), alg="HS256"))

    def test_malformed_tokens_are_rejected(self) -> None:
        for token in ("", "abc", "a.b", "a.b.c.d", "###.###.###", "e30.e30.e30"):
            with self.subTest(token=token):
                self._rejected(token)

    def test_unknown_key_id_is_rejected(self) -> None:
        self._rejected(ROTATED_KEY.sign(_claims()))

    def test_keys_are_cached_between_requests(self) -> None:
        for _ in range(3):
            self.verifier.verify(KEY.sign(_claims()))
        self.assertEqual(self.jwks.calls, 1)

    def test_rotated_key_is_fetched_after_the_minimum_interval(self) -> None:
        self.verifier.verify(KEY.sign(_claims()))
        self.jwks.keys.append(ROTATED_KEY)
        token = ROTATED_KEY.sign(_claims(exp=NOW + 3600))
        self._rejected(token)
        self.assertEqual(self.jwks.calls, 1)
        self.clock.now += 11
        self.assertEqual(self.verifier.verify(token).id, "3f0e5d0a-user")
        self.assertEqual(self.jwks.calls, 2)

    def test_keycloak_down_on_first_use_rejects_the_token(self) -> None:
        self.jwks.fail = True
        with self.assertLogs("src.infrastructure.auth", level="WARNING"):
            self._rejected(KEY.sign(_claims()))

    def test_keycloak_down_later_keeps_the_known_keys(self) -> None:
        self.verifier.verify(KEY.sign(_claims()))
        self.jwks.fail = True
        self.clock.now += 301
        token = KEY.sign(_claims(exp=NOW + 3600))
        with self.assertLogs("src.infrastructure.auth", level="WARNING"):
            self.assertEqual(self.verifier.verify(token).id, "3f0e5d0a-user")

    def test_issuer_is_built_from_url_and_realm(self) -> None:
        self.assertEqual(issuer_url("http://localhost:8080/", "nexus"), ISSUER)


if __name__ == "__main__":
    unittest.main()
