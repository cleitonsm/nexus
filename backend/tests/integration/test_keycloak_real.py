"""CT-52 (RNF-22, RF-40, RF-41): tokens reais do Keycloak do Compose.

Usa o cliente ``nexus-tests`` do realm de desenvolvimento (V-D2). Token valido
e aceito; adulterado ou de assinatura alheia responde 401; papeis e grupos do
token chegam a politica. A expiracao (``exp``) e coberta com chave local em
``tests/unit/test_token_verifier.py``; aqui nao ha como emitir um token vencido
sem alterar o realm.
"""

from __future__ import annotations

import base64
import json
import unittest

from stack_support import Api, stack_available, token_for


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _forged(token: str, claims: dict, *, alg: str = "RS256") -> str:
    header, payload, signature = token.split(".")
    decoded = json.loads(
        base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
    )
    decoded.update(claims)
    new_header = _b64(json.dumps({"alg": alg, "typ": "JWT"}).encode())
    return ".".join([new_header, _b64(json.dumps(decoded).encode()), signature])


class KeycloakRealTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        if not stack_available():
            self.skipTest("pilha do Compose indisponivel")
        try:
            self.token = token_for("usuario.rh")
        except Exception:  # noqa: BLE001 - realm sem o cliente de testes
            self.skipTest("Keycloak ou cliente nexus-tests indisponivel")

    def test_valid_token_is_accepted_with_roles_and_groups(self) -> None:
        status, me = Api(self.token).json("GET", "/me")
        self.assertEqual(status, 200, me)
        self.assertIn("rh", {group.strip("/") for group in me["groups"]})
        self.assertNotIn("nexus-admin", me["roles"])

    def test_admin_role_reaches_policy(self) -> None:
        status, me = Api(token_for("admin.nexus")).json("GET", "/me")
        self.assertEqual(status, 200, me)
        # Papeis de realm do Keycloak (Role, RF-41), sem traducao na API.
        self.assertIn("nexus-admin", me["roles"])
        status, _ = Api(self.token).json("GET", "/admin/llm-credentials")
        self.assertEqual(status, 403)

    def test_tampered_payload_is_rejected(self) -> None:
        forged = _forged(self.token, {"realm_access": {"roles": ["nexus-admin"]}})
        status, _ = Api(forged).json("GET", "/me")
        self.assertEqual(status, 401)

    def test_other_issuer_is_rejected(self) -> None:
        forged = _forged(self.token, {"iss": "http://outro-realm/realms/x"})
        status, _ = Api(forged).json("GET", "/me")
        self.assertEqual(status, 401)

    def test_unsigned_and_garbage_tokens_are_rejected(self) -> None:
        unsigned = _forged(self.token, {}, alg="none")
        for token in (unsigned, "nao-e-um-jwt", ""):
            with self.subTest(token=token[:12]):
                status, _ = Api(token).json("GET", "/me")
                self.assertEqual(status, 401)

    def test_missing_token_is_rejected(self) -> None:
        from stack_support import API_URL, call

        self.assertEqual(call("GET", f"{API_URL}/me")[0], 401)


class GroupDirectoryRealTests(unittest.TestCase):
    """SPEC-009 D5: a lista de grupos vem do Keycloak real, nao vazia.

    Com so ``query-groups`` a conta de servico recebia 200 e lista vazia, e todo
    envio com grupo era recusado (achado do CT-56, 2026-10-20).
    """

    def setUp(self) -> None:
        if not stack_available():
            self.skipTest("pilha do Compose indisponivel")
        try:
            self.admin = Api(token_for("admin.nexus"))
        except Exception:  # noqa: BLE001 - realm sem o cliente de testes
            self.skipTest("Keycloak ou cliente nexus-tests indisponivel")

    def test_groups_of_the_realm_are_listed(self) -> None:
        status, groups = self.admin.json("GET", "/groups")
        self.assertEqual(status, 200, groups)
        self.assertTrue(
            {"rh", "financeiro", "diretoria"} <= set(groups),
            f"lista do Keycloak: {groups} (falta view-users na conta de servico?)",
        )


if __name__ == "__main__":
    unittest.main()
