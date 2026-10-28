"""CT-39 (RF-53): OCR em portugues dentro do container.

Gera um PDF so de imagem (sem camada de texto) com frases em portugues, envia
pela API e confere que chega a ``indexado`` e que uma pergunta por termo com
acento recupera o trecho. Exige a pilha no ar, o Tesseract com o idioma
``por`` (imagem do backend) e o Pillow. O LLM e simulado.
"""

from __future__ import annotations

import io
import json
import os
import unittest
from uuid import uuid4

from stack_support import (
    Api,
    FakeLLMServer,
    call,
    use_fake_llm,
    stack_available,
    token_for,
)

LINES = [
    "Politica de reembolso de despesas de viagem",
    "A aprovação do gestor é obrigatória antes da viagem.",
    "A prestação de contas ocorre em até cinco dias úteis.",
    "Despesas sem comprovação fiscal não serão reembolsadas.",
]


FONT_CANDIDATES = (
    os.getenv("OCR_TEST_FONT", ""),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "DejaVuSans.ttf",
    "LiberationSans-Regular.ttf",
)
ACCENTED = "ãçéúáóêí"


def _accented_font(size: int):
    """Fonte TrueType que desenha os acentos.

    A fonte embutida do Pillow nao tem esses glifos: cada um sai como o
    quadrado de glifo ausente, que o Tesseract le como ``X`` ou ``k``.
    """
    from PIL import ImageFont

    for candidate in FONT_CANDIDATES:
        if not candidate:
            continue
        try:
            font = ImageFont.truetype(candidate, size)
        except OSError:
            continue
        missing = bytes(font.getmask("\ue000"))
        if all(bytes(font.getmask(char)) != missing for char in ACCENTED):
            return font
    raise RuntimeError(
        "nenhuma fonte TrueType com acentos (defina OCR_TEST_FONT)"
    )


def _scanned_pdf() -> bytes:
    from PIL import Image, ImageDraw

    font = _accented_font(44)
    image = Image.new("RGB", (1654, 2339), "white")
    draw = ImageDraw.Draw(image)
    for row, line in enumerate(LINES):
        draw.text((120, 200 + row * 120), line, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, "PDF", resolution=200)
    return buffer.getvalue()


def _indexed_chunks(assistant_id: str) -> str:
    """Trechos gravados no Qdrant, para diagnosticar uma recuperacao vazia."""
    url = os.getenv("QDRANT_URL", "http://qdrant:6333").rstrip("/")
    headers = {"Content-Type": "application/json"}
    if os.getenv("QDRANT_API_KEY"):
        headers["api-key"] = os.environ["QDRANT_API_KEY"]
    try:
        status, _, payload = call(
            "POST",
            f"{url}/collections/assistant-{assistant_id}/points/scroll",
            headers=headers,
            body=json.dumps(
                {"limit": 20, "with_payload": True, "with_vector": False}
            ).encode(),
        )
    except OSError as exc:
        return f"Qdrant inacessivel: {exc}"
    return f"Qdrant {status}: {payload.decode('utf-8', 'replace')[:3000]}"


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
            use_fake_llm(self, self.admin, llm.url, self.assistant_id)
            status, conversation = self.admin.json(
                "POST", "/conversations", payload={"assistant_id": self.assistant_id}
            )
            self.assertEqual(status, 201, conversation)
            status, answer = self.admin.json(
                "POST",
                f"/conversations/{conversation['id']}/chat",
                # Pergunta especifica: o teste cobre OCR, indexacao e recuperacao, nao a
                # calibracao. Com a forma curta ("Qual o prazo da prestação de
                # contas?") este trecho recebe ~0,19 do reranker e cai sob o
                # RELEVANCE_MIN_SCORE de 0,5 (ver scripts/diagnostico_reranker.py).
                payload={
                    "question": (
                        "Qual o prazo para a prestação de contas das despesas "
                        "de viagem?"
                    )
                },
            )
            self.assertEqual(status, 201, answer)
        citations = answer["assistant_message"]["citations"]
        self.assertTrue(
            citations,
            f"{answer} | RELEVANCE_MIN_SCORE={os.getenv('RELEVANCE_MIN_SCORE')} | "
            f"{_indexed_chunks(self.assistant_id)}",
        )
        self.assertEqual(citations[0]["source_name"], "digitalizado.pdf")
        self.assertIn("úteis", " ".join(item["excerpt"] for item in citations))


if __name__ == "__main__":
    unittest.main()
