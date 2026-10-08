"""PC-D6: lista de grupos do Keycloak para administrador e curador."""

from __future__ import annotations

import unittest
from urllib import error

from access_doubles import AccessFixture, admin, curator, make_user

from src.application.use_cases import ListAvailableGroupsUseCase
from src.domain import AccessDeniedError, GroupDirectoryUnavailableError
from src.infrastructure.auth import KeycloakGroupDirectory

BASE = "http://keycloak:8080"
TOKEN_URL = f"{BASE}/realms/nexus/protocol/openid-connect/token"
GROUPS_URL = f"{BASE}/admin/realms/nexus/groups"


class FakeKeycloak:
    def __init__(self) -> None:
        self.token_calls: list[dict[str, str]] = []
        self.get_calls: list[str] = []
        self.fail_with: Exception | None = None
        self.pages: dict[str, list] = {
            f"{GROUPS_URL}?briefRepresentation=true": [
                {"id": "g1", "name": "rh", "subGroupCount": 0},
                {"id": "g2", "name": "Diretoria", "subGroupCount": 1},
                {"id": "g3", "name": "financeiro", "subGroups": [
                    {"id": "g4", "name": "contabilidade", "subGroupCount": 0}
                ]},
            ],
            f"{GROUPS_URL}/g2/children?briefRepresentation=true": [
                {"id": "g5", "name": "conselho", "subGroupCount": 0}
            ],
        }

    def post_form(self, url: str, fields: dict[str, str]) -> dict[str, object]:
        if self.fail_with:
            raise self.fail_with
        assert url == TOKEN_URL
        self.token_calls.append(fields)
        return {"access_token": "token-1", "expires_in": 300}

    def get_json(self, url: str, token: str) -> object:
        assert token == "token-1"
        self.get_calls.append(url)
        base, _, query = url.partition("&first=")
        first = int(query.split("&")[0])
        return self.pages.get(base, [])[first:] if first == 0 else []


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def directory(fake: FakeKeycloak, clock: Clock | None = None, secret: str = "s3cret"):
    return KeycloakGroupDirectory(
        base_url=BASE + "/",
        realm="nexus",
        client_id="nexus-backend",
        client_secret=secret,
        post_form=fake.post_form,
        get_json=fake.get_json,
        clock=clock or Clock(),
        cache_seconds=60,
    )


class KeycloakGroupDirectoryTestCase(unittest.TestCase):
    def test_lists_groups_and_subgroups_sorted(self) -> None:
        fake = FakeKeycloak()
        self.assertEqual(
            directory(fake).list_groups(),
            ["conselho", "contabilidade", "Diretoria", "financeiro", "rh"],
        )
        self.assertEqual(fake.token_calls[0]["grant_type"], "client_credentials")
        self.assertEqual(fake.token_calls[0]["client_id"], "nexus-backend")

    def test_list_is_cached_and_refreshed_after_the_ttl(self) -> None:
        fake, clock = FakeKeycloak(), Clock()
        groups = directory(fake, clock)
        groups.list_groups()
        calls = len(fake.get_calls)
        groups.list_groups()
        self.assertEqual(len(fake.get_calls), calls)
        clock.now += 61
        groups.list_groups()
        self.assertGreater(len(fake.get_calls), calls)
        self.assertEqual(len(fake.token_calls), 1)

    def test_without_secret_the_directory_is_unavailable(self) -> None:
        fake = FakeKeycloak()
        with self.assertRaises(GroupDirectoryUnavailableError):
            directory(fake, secret="").list_groups()
        self.assertEqual(fake.token_calls, [])

    def test_network_or_credential_failure_is_unavailable_without_the_secret(self) -> None:
        fake = FakeKeycloak()
        fake.fail_with = error.HTTPError(TOKEN_URL, 401, "Unauthorized", None, None)
        with self.assertRaises(GroupDirectoryUnavailableError) as raised:
            directory(fake).list_groups()
        self.assertNotIn("s3cret", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)


class StaticDirectory:
    def __init__(self, names=None, fail=False) -> None:
        self.names = names or []
        self.fail = fail

    def list_groups(self) -> list[str]:
        if self.fail:
            raise GroupDirectoryUnavailableError("down")
        return list(self.names)


class ListAvailableGroupsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.access = AccessFixture()

    def test_admin_and_curator_get_clean_unique_names(self) -> None:
        use_case = ListAvailableGroupsUseCase(
            StaticDirectory(["rh", " rh ", "", "Diretoria", "financeiro"]),
            self.access.control,
        )
        for user in (admin(), curator("curadora", "rh")):
            with self.subTest(user=user.id):
                self.assertEqual(use_case.execute(user), ["Diretoria", "financeiro", "rh"])

    def test_common_user_is_denied_and_audited(self) -> None:
        with self.assertRaises(AccessDeniedError):
            ListAvailableGroupsUseCase(StaticDirectory(["rh"]), self.access.control).execute(
                make_user("user-1", groups=("rh",))
            )
        self.assertIn("access.denied", self.access.audit.actions())

    def test_unavailable_directory_propagates(self) -> None:
        with self.assertRaises(GroupDirectoryUnavailableError):
            ListAvailableGroupsUseCase(
                StaticDirectory(fail=True), self.access.control
            ).execute(admin())


if __name__ == "__main__":
    unittest.main()
