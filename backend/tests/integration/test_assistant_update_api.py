"""CT-134 (SPEC-017): PUT /assistants/{id} e o prompt em GET /assistants.

Repositorios em memoria e identidade dublada, como o CT-127; nao precisa do
Keycloak nem do banco. Execute dentro do container do backend.
"""

from __future__ import annotations

import json
import unittest
from dataclasses import replace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from access_support import ADMIN, AccessHarness, member
from src.api.dependencies import get_assistant_repository, get_default_llm_gateway
from src.api.errors import register_error_handlers
from src.api.routes.assistants import router as assistants_router
from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    AuditAction,
    LLMCredentialId,
    Role,
)

CURATOR = member("curador-juridico", "juridico", role=Role.CURATOR)
OTHER_CURATOR = member("curador-financeiro", "financeiro", role=Role.CURATOR)
USER = member("usuario-juridico", "juridico")
BODY = {
    "name": "Juridico e Contratos",
    "description": "Contratos e pareceres",
    "initial_prompt": "Responda em topicos.",
}


class _Assistants:
    def __init__(self) -> None:
        self.items: dict[str, Assistant] = {}

    def save(self, assistant: Assistant) -> Assistant:
        self.items[assistant.id.value] = assistant
        return assistant

    def update_profile(self, assistant_id, *, name, description, initial_prompt):
        current = self.items.get(assistant_id.value)
        if current is None:
            return None
        updated = replace(
            current, name=name, description=description, initial_prompt=initial_prompt
        )
        self.items[assistant_id.value] = updated
        return updated

    def list_all(self) -> list[Assistant]:
        return list(self.items.values())

    def get_by_id(self, assistant_id: AssistantId) -> Assistant | None:
        return self.items.get(assistant_id.value)


class _RecordingLLM:
    """Guarda o prompt da inferencia e escolhe o primeiro candidato."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, *, prompt: str, context_chunks, conversation_history) -> str:
        self.prompts.append(prompt)
        return '{"assistant_id": "juridico"}'


class AssistantUpdateApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        register_error_handlers(self.app)
        self.app.include_router(assistants_router)
        self.access = AccessHarness(self.app, ADMIN)
        self.assistants = _Assistants()
        self.assistants.save(
            Assistant(
                id=AssistantId("juridico"),
                name=AssistantName("Assistente juridico"),
                description="Contratos",
                initial_prompt="Aja como advogado.",
                llm_credential_id=LLMCredentialId("cred-1"),
                llm_model="gpt-4o-mini",
            )
        )
        self.access.link_assistant("juridico", "juridico")
        self.app.dependency_overrides[get_assistant_repository] = lambda: self.assistants
        self.client = TestClient(self.app)

    def _put(self, assistant_id: str = "juridico", **fields):
        return self.client.put(f"/assistants/{assistant_id}", json={**BODY, **fields})

    def test_admin_updates_and_keeps_groups_and_llm(self) -> None:
        response = self._put()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["name"], "Juridico e Contratos")
        self.assertEqual(body["initial_prompt"], "Responda em topicos.")
        self.assertEqual(body["groups"], ["juridico"])
        stored = self.assistants.items["juridico"]
        self.assertEqual(stored.llm_credential_id, LLMCredentialId("cred-1"))
        self.assertEqual(stored.llm_model, "gpt-4o-mini")
        self.assertIn(AuditAction.ASSISTANT_UPDATED, self.access.audit.actions())

    def test_curator_of_the_assistant_updates(self) -> None:
        self.access.user = CURATOR
        self.assertEqual(self._put().status_code, 200)

    def test_others_get_403_and_are_audited(self) -> None:
        for user in (USER, OTHER_CURATOR):
            with self.subTest(user=user.id):
                self.access.user = user
                response = self._put()
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["code"], "forbidden")
                self.assertEqual(self.access.audit.actions()[-1], AuditAction.ACCESS_DENIED)
        self.assertEqual(self.assistants.items["juridico"].name.value, "Assistente juridico")

    def test_missing_assistant(self) -> None:
        response = self._put("nao-existe")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "assistant_not_found")
        self.access.user = CURATOR
        self.assertEqual(self._put("nao-existe").status_code, 403)
        self.assertNotIn("nao-existe", self.assistants.items)

    def test_rule_violations_are_422_with_code_and_no_echo(self) -> None:
        cases = (
            ({"name": "   "}, "assistant_name_required"),
            ({"name": "n" * 81}, "assistant_name_too_long"),
            ({"description": "d" * 501}, "assistant_description_too_long"),
            ({"initial_prompt": "SEGREDO-" + "p" * 4000}, "assistant_prompt_too_long"),
        )
        for fields, code in cases:
            with self.subTest(code=code):
                response = self._put(**fields)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["code"], code)
                self.assertNotIn("SEGREDO", response.text)
        self.assertEqual(self.assistants.items["juridico"].name.value, "Assistente juridico")

    def test_malformed_body_is_422(self) -> None:
        response = self.client.put("/assistants/juridico", json={"description": "x"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["code"], "validation_error")

    def test_empty_prompt_is_cleared(self) -> None:
        response = self._put(initial_prompt="  ", description="")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["initial_prompt"])
        self.assertIsNone(response.json()["description"])

    def test_audit_event_carries_no_text(self) -> None:
        self._put()
        event = next(
            item for item in self.access.audit.events
            if item.action == AuditAction.ASSISTANT_UPDATED
        )
        dumped = json.dumps(event.details)
        self.assertNotIn("Responda em topicos", dumped)
        self.assertNotIn("Aja como advogado", dumped)

    def test_inference_still_sees_the_prompt_for_a_common_user(self) -> None:
        """D5 esconde o prompt da listagem, nao da escolha automatica."""
        llm = _RecordingLLM()
        self.app.dependency_overrides[get_default_llm_gateway] = lambda: llm
        self.access.user = USER
        response = self.client.post("/assistants/infer", json={"question": "Como rescindir?"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"assistant_id": "juridico"})
        self.assertIn("Aja como advogado.", llm.prompts[0])
        self.assertNotIn("Aja como advogado.", self.client.get("/assistants").text)

    def test_prompt_only_for_editors_in_the_listing(self) -> None:
        """D5 (RF-111)."""
        expected = {ADMIN.id: "Aja como advogado.", CURATOR.id: "Aja como advogado.", USER.id: None}
        for user in (ADMIN, CURATOR, USER):
            with self.subTest(user=user.id):
                self.access.user = user
                listed = self.client.get("/assistants").json()
                self.assertEqual(listed[0]["initial_prompt"], expected[user.id])


if __name__ == "__main__":
    unittest.main()
