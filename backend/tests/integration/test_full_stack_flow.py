"""CT-50 (RF-37, RF-48 a RF-50, D10): fluxo completo na pilha real.

Criar assistente -> enviar documento -> ``indexado`` -> perguntar -> resposta
com citacao -> excluir o documento -> citacao com ``document_available`` falso.
O LLM e simulado por um servidor HTTP criado no teste (``stack_support``).
Exige a pilha no ar e o realm de desenvolvimento; o provedor ``custom`` com URL
``http`` so e aceito com a documentacao da API habilitada (ambiente local).
Altera a conexao do LLM e a restaura ao final.
"""

from __future__ import annotations

import unittest
from uuid import uuid4

from stack_support import Api, FakeLLMServer, stack_available, token_for

DOCUMENT = (
    "# Ferias\n\nO colaborador tem trinta dias corridos de ferias por ano, "
    "que podem ser divididos em ate tres periodos.\n"
)


class FullStackFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        if not stack_available():
            self.skipTest("pilha do Compose indisponivel")
        self.admin = Api(token_for("admin.nexus"))
        status, original = self.admin.json("GET", "/admin/llm-settings")
        self.assertEqual(status, 200)
        self.original = original
        self.addCleanup(self._restore_llm)
        self.created: list[str] = []
        self.addCleanup(self._remove_assistants)

    def _restore_llm(self) -> None:
        payload = {
            "provider": self.original["provider"],
            "model": self.original["model"],
        }
        if self.original["provider"] == "custom":
            payload["api_url"] = self.original["api_url"]
        self.admin.json("PUT", "/admin/llm-settings", payload=payload)

    def _remove_assistants(self) -> None:
        for assistant_id in self.created:
            self.admin.request("DELETE", f"/assistants/{assistant_id}")

    def _assistant(self) -> str:
        status, data = self.admin.json(
            "POST", "/assistants", payload={"name": f"CT-50 {uuid4().hex[:8]}"}
        )
        self.assertEqual(status, 201, data)
        self.created.append(data["id"])
        return data["id"]

    def test_upload_ask_cite_and_delete(self) -> None:
        assistant_id = self._assistant()
        status, document = self.admin.upload(
            assistant_id, "ferias.md", DOCUMENT.encode()
        )
        self.assertEqual(status, 202, document)
        done = self.admin.wait_indexed(document["id"])
        self.assertEqual(done["status"], "indexado", done)

        with FakeLLMServer() as llm:
            status, data = self.admin.json(
                "PUT",
                "/admin/llm-settings",
                payload={
                    "provider": "custom",
                    "model": "modelo-simulado",
                    "api_url": llm.url,
                },
            )
            self.assertEqual(status, 200, data)
            status, conversation = self.admin.json(
                "POST", "/conversations", payload={"assistant_id": assistant_id}
            )
            self.assertEqual(status, 201, conversation)
            conversation_id = conversation["id"]
            status, answer = self.admin.json(
                "POST",
                f"/conversations/{conversation_id}/chat",
                payload={"question": "Quantos dias de ferias o colaborador tem?"},
            )
            self.assertEqual(status, 201, answer)
            self.assertTrue(llm.requests, "o LLM simulado nao foi chamado")
        citations = answer["assistant_message"]["citations"]
        self.assertTrue(citations, answer)
        self.assertEqual(citations[0]["source_name"], "ferias.md")
        self.assertTrue(citations[0]["document_available"])

        status, _, _ = self.admin.request("DELETE", f"/documents/{document['id']}")
        self.assertEqual(status, 204)
        status, detail = self.admin.json("GET", f"/conversations/{conversation_id}")
        self.assertEqual(status, 200)
        cited = [
            citation
            for message in detail["messages"]
            for citation in message["citations"]
        ]
        self.assertTrue(cited)
        self.assertFalse(any(item["document_available"] for item in cited))


if __name__ == "__main__":
    unittest.main()
