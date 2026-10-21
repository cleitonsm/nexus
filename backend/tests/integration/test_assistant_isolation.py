"""CT-51 (RNF-07, RNF-08): isolamento entre assistentes na pilha real.

Dois assistentes com documentos distintos nao se misturam na busca; excluir o
assistente remove a collection e o alias no Qdrant. Exige a pilha no ar.
"""

from __future__ import annotations

import json
import os
import unittest
from uuid import uuid4

from stack_support import (
    Api,
    FakeLLMServer,
    call,
    preserve_llm_settings,
    stack_available,
    token_for,
)

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333").rstrip("/")
QDRANT_HEADERS = {"api-key": os.getenv("QDRANT_API_KEY", "nexus-local")}

DOCS = {
    "ferias.md": "# Ferias\n\nO colaborador tem trinta dias corridos de ferias por ano.\n",
    "estacionamento.md": "# Estacionamento\n\nO estacionamento da matriz abre as sete horas e fecha as vinte horas.\n",
}


def _aliases() -> set[str]:
    status, _, body = call(
        "GET", f"{QDRANT_URL}/aliases", headers=QDRANT_HEADERS
    )
    if status != 200:
        raise RuntimeError(f"qdrant aliases failed ({status}).")
    return {item["alias_name"] for item in json.loads(body)["result"]["aliases"]}


class AssistantIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        if not stack_available():
            self.skipTest("pilha do Compose indisponivel")
        self.admin = Api(token_for("admin.nexus"))
        preserve_llm_settings(self, self.admin)
        self.ids: list[str] = []
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        for assistant_id in self.ids:
            self.admin.request("DELETE", f"/assistants/{assistant_id}")

    def _assistant_with(self, name: str, content: str) -> tuple[str, str]:
        status, data = self.admin.json(
            "POST", "/assistants", payload={"name": f"CT-51 {uuid4().hex[:8]}"}
        )
        self.assertEqual(status, 201, data)
        self.ids.append(data["id"])
        status, document = self.admin.upload(data["id"], name, content.encode())
        self.assertEqual(status, 202, document)
        done = self.admin.wait_indexed(document["id"])
        self.assertEqual(done["status"], "indexado", done)
        return data["id"], document["id"]

    def _ask(self, assistant_id: str, question: str) -> dict:
        status, conversation = self.admin.json(
            "POST", "/conversations", payload={"assistant_id": assistant_id}
        )
        self.assertEqual(status, 201, conversation)
        status, answer = self.admin.json(
            "POST",
            f"/conversations/{conversation['id']}/chat",
            payload={"question": question},
        )
        self.assertEqual(status, 201, answer)
        return answer

    def test_assistants_do_not_mix_and_delete_removes_collection(self) -> None:
        first, _ = self._assistant_with("ferias.md", DOCS["ferias.md"])
        second, _ = self._assistant_with("estacionamento.md", DOCS["estacionamento.md"])
        with FakeLLMServer() as llm:
            self.admin.json(
                "PUT",
                "/admin/llm-settings",
                payload={
                    "provider": "custom",
                    "model": "modelo-simulado",
                    "api_url": llm.url,
                },
            )
            first_answer = self._ask(first, "Que horas abre o estacionamento?")
            second_answer = self._ask(second, "Quantos dias de ferias?")
        for answer, foreign in (
            (first_answer, "estacionamento.md"),
            (second_answer, "ferias.md"),
        ):
            sources = {
                item["source_name"]
                for item in answer["assistant_message"]["citations"]
            }
            self.assertNotIn(foreign, sources)

        self.assertIn(f"assistant-{first}", _aliases())
        status, _, _ = self.admin.request("DELETE", f"/assistants/{first}")
        self.assertEqual(status, 204)
        self.ids.remove(first)
        aliases = _aliases()
        self.assertNotIn(f"assistant-{first}", aliases)
        self.assertIn(f"assistant-{second}", aliases)
        status, _, _ = call(
            "GET",
            f"{QDRANT_URL}/collections/assistant-{first}-v2",
            headers=QDRANT_HEADERS,
        )
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
