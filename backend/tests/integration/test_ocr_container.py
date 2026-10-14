"""CT-39 (RF-53): OCR em portugues dentro do container.

Gera um PDF so de imagem (sem camada de texto) com frases em portugues, envia
pela API e confere que chega a ``indexado`` e que uma pergunta por termo com
acento recupera o trecho. Exige a pilha no ar, o Tesseract com o idioma
``por`` (imagem do backend) e o Pillow. O LLM e simulado.
"""

from __future__ import annotations

import io
import unittest
from uuid import uuid4

from stack_support import Api, FakeLLMServer, stack_available, token_for

LINES = [
    "Politica de reembolso de despesas de viagem",
    "A aprovação do gestor é obrigatória antes da viagem.",
    "A prestação de contas ocorre em até cinco dias úteis.",
    "Despesas sem comprovação fiscal não serão reembolsadas.",
]


def _scanned_pdf() -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.load_default(size=44)
    image = Image.new("RGB", (1654, 2339), "white")
    draw = ImageDraw.Draw(image)
    for row, line in enumerate(LINES):
        draw.text((120, 200 + row * 120), line, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, "PDF", resolution=200)
    return buffer.getvalue()


class OcrContainerTests(unittest.TestCase):
    def setUp(self) -> None:
        if not stack_available():
            self.skipTest("pilha do Compose indisponivel")
        try:
            self.pdf = _scanned_pdf()
        except Exception as exc:  # noqa: BLE001 - sem Pillow ou fonte
            self.skipTest(f"nao foi possivel gerar o PDF digitalizado: {exc}")
        self.admin = Api(token_for("admin.nexus"))
        status, data = self.admin.json(
            "POST", "/assistants", payload={"name": f"CT-39 {uuid4().hex[:8]}"}
        )
        self.assertEqual(status, 201, data)
        self.assistant_id = data["id"]
        self.addCleanup(
            lambda: self.admin.request("DELETE", f"/assistants/{self.assistant_id}")
        )

    def test_scanned_portuguese_pdf_is_indexed_and_retrievable(self) -> None:
        status, document = self.admin.upload(
            self.assistant_id,
            "digitalizado.pdf",
            self.pdf,
            content_type="application/pdf",
        )
        self.assertEqual(status, 202, document)
        done = self.admin.wait_indexed(document["id"])
        self.assertEqual(done["status"], "indexado", done)
        self.assertGreater(done["chunk_count"], 0)

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
            status, conversation = self.admin.json(
                "POST", "/conversations", payload={"assistant_id": self.assistant_id}
            )
            self.assertEqual(status, 201, conversation)
            status, answer = self.admin.json(
                "POST",
                f"/conversations/{conversation['id']}/chat",
                payload={"question": "Qual o prazo da prestação de contas?"},
            )
            self.assertEqual(status, 201, answer)
        citations = answer["assistant_message"]["citations"]
        self.assertTrue(citations, answer)
        self.assertEqual(citations[0]["source_name"], "digitalizado.pdf")
        self.assertIn("úteis", " ".join(item["excerpt"] for item in citations))


if __name__ == "__main__":
    unittest.main()
