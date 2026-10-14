"""CT-57 (R18): a conferencia PostgreSQL x Qdrant aponta ponto apagado.

Envia um documento pela API, confirma a conferencia limpa, apaga um ponto
direto no Qdrant e espera divergencia (codigo 1). Exige a pilha no ar e deve
rodar no container do backend (usa o mesmo banco e o mesmo Qdrant).
"""

from __future__ import annotations

import json
import os
import unittest
from uuid import uuid4

from stack_support import Api, call, stack_available, token_for

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333").rstrip("/")
HEADERS = {
    "api-key": os.getenv("QDRANT_API_KEY", "nexus-local"),
    "Content-Type": "application/json",
}
TEXT = "# Reembolso\n\nO reembolso de viagem e pedido no sistema financeiro, com nota fiscal.\n"


class ConsistencyCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        if not stack_available():
            self.skipTest("pilha do Compose indisponivel")
        self.admin = Api(token_for("admin.nexus"))
        status, data = self.admin.json(
            "POST", "/assistants", payload={"name": f"CT-57 {uuid4().hex[:8]}"}
        )
        self.assertEqual(status, 201, data)
        self.assistant_id = data["id"]
        self.addCleanup(
            lambda: self.admin.request("DELETE", f"/assistants/{self.assistant_id}")
        )

    def _check(self) -> int:
        from src.cli.check_consistency import main

        return main(["--assistant", self.assistant_id])

    def test_deleted_point_is_reported(self) -> None:
        status, document = self.admin.upload(
            self.assistant_id, "reembolso.md", TEXT.encode()
        )
        self.assertEqual(status, 202, document)
        self.assertEqual(self.admin.wait_indexed(document["id"])["status"], "indexado")
        self.assertEqual(self._check(), 0)

        collection = f"assistant-{self.assistant_id}"
        status, _, body = call(
            "POST",
            f"{QDRANT_URL}/collections/{collection}/points/scroll",
            headers=HEADERS,
            body=json.dumps({"limit": 1, "with_payload": False}).encode(),
        )
        self.assertEqual(status, 200, body)
        point_id = json.loads(body)["result"]["points"][0]["id"]
        status, _, body = call(
            "POST",
            f"{QDRANT_URL}/collections/{collection}/points/delete?wait=true",
            headers=HEADERS,
            body=json.dumps({"points": [point_id]}).encode(),
        )
        self.assertEqual(status, 200, body)
        self.assertEqual(self._check(), 1)


if __name__ == "__main__":
    unittest.main()
