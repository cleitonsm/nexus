"""CT-127 (SPEC-016): GET/PUT /me/home-assistants pela API.

Repositorios em memoria e identidade dublada, como o CT-30; nao precisa do
Keycloak nem do banco. Execute dentro do container do backend.
"""

from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from access_support import AccessHarness, member
from src.api.dependencies import get_assistant_repository, get_home_assistant_repository
from src.api.routes.me import router as me_router
from src.domain import Assistant, AssistantId, AssistantName, HomeAssistantSelection

ANA = member("ana", "todos")
BRUNO = member("bruno", "todos")
ROUTE = "/me/home-assistants"


class _Assistants:
    def __init__(self, *ids: str) -> None:
        self.items = {item: Assistant(id=AssistantId(item), name=AssistantName(item)) for item in ids}

    def list_all(self) -> list[Assistant]:
        return list(self.items.values())


class _Preferences:
    def __init__(self) -> None:
        self.saved: dict[str, HomeAssistantSelection] = {}

    def get(self, owner_user_id: str) -> HomeAssistantSelection | None:
        return self.saved.get(owner_user_id)

    def replace(self, owner_user_id: str, selection: HomeAssistantSelection) -> None:
        self.saved[owner_user_id] = selection


class HomeAssistantsApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(me_router)
        self.access = AccessHarness(self.app, ANA)
        for assistant_id in ("normativo", "juridico", "financeiro", "rh", "ti"):
            self.access.link_assistant(assistant_id, "todos")
        self.access.link_assistant("restrito", "diretoria")
        self.assistants = _Assistants("normativo", "juridico", "financeiro", "rh", "ti", "restrito")
        self.preferences = _Preferences()
        overrides = self.app.dependency_overrides
        overrides[get_assistant_repository] = lambda: self.assistants
        overrides[get_home_assistant_repository] = lambda: self.preferences
        self.client = TestClient(self.app)

    def _put(self, ids: list[str], default: str):
        return self.client.put(ROUTE, json={"assistant_ids": ids, "default_assistant_id": default})

    def test_get_without_preference(self) -> None:
        response = self.client.get(ROUTE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "assistant_ids": ["normativo", "juridico", "financeiro", "rh"],
                "default_assistant_id": "normativo",
                "max": 4,
                "customized": False,
            },
        )

    def test_put_then_get(self) -> None:
        response = self._put(["juridico", "financeiro"], "financeiro")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["assistant_ids"], ["financeiro", "juridico"])
        self.assertEqual(self.client.get(ROUTE).json(), response.json())

    def test_rule_violations_are_422_with_code(self) -> None:
        cases = (
            ([], "normativo", "home_assistants_empty"),
            (["normativo", "juridico", "financeiro", "rh", "ti"], "ti", "home_assistants_limit"),
            (["rh", "rh"], "rh", "home_assistants_duplicate"),
            (["rh"], "ti", "home_assistants_default_not_selected"),
            (["restrito"], "restrito", "assistant_not_available"),
            (["nao-existe"], "nao-existe", "assistant_not_available"),
            (["  "], "  ", "assistant_not_available"),
        )
        for ids, default, code in cases:
            with self.subTest(code=code, ids=ids):
                response = self._put(ids, default)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["code"], code)
        self.assertEqual(self.preferences.saved, {})

    def test_malformed_body_is_422(self) -> None:
        response = self.client.put(ROUTE, json={"assistant_ids": ["rh"]})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["code"], "validation_error")

    def test_users_are_isolated(self) -> None:
        """RF-106: o dono e sempre o usuario do token."""
        self._put(["ti"], "ti")
        self.access.user = BRUNO
        self.assertFalse(self.client.get(ROUTE).json()["customized"])
        self._put(["rh"], "rh")
        self.access.user = ANA
        self.assertEqual(self.client.get(ROUTE).json()["assistant_ids"], ["ti"])

    def test_lost_group_filters_on_read(self) -> None:
        """D8."""
        self._put(["juridico", "normativo"], "juridico")
        self.access.link_assistant("juridico", "outro")
        body = self.client.get(ROUTE).json()
        self.assertEqual(body["assistant_ids"], ["normativo"])
        self.assertEqual(body["default_assistant_id"], "normativo")

    def test_user_without_assistants(self) -> None:
        self.access.user = member("zeca", "nenhum")
        body = self.client.get(ROUTE).json()
        self.assertEqual(body["assistant_ids"], [])
        self.assertIsNone(body["default_assistant_id"])

    def test_preference_is_not_audited(self) -> None:
        """RN-50."""
        self._put(["restrito"], "restrito")
        self._put(["rh"], "rh")
        self.assertEqual(self.access.audit.events, [])


if __name__ == "__main__":
    unittest.main()
