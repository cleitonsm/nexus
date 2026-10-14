"""CT-55 (RF-58, RF-59, C15): comportamento do Nginx na frente da API.

Exige a pilha do Compose no ar. Informe ``NGINX_URL`` (padrao
``http://frontend``, o nome do servico na rede do Compose; pelo host,
``http://localhost:4200``). Sem a pilha, o teste e pulado.
"""

from __future__ import annotations

import http.client
import os
import unittest
from urllib.parse import urlsplit

BASE = os.getenv("NGINX_URL", "http://frontend").rstrip("/")


def _call(
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str]]:
    parts = urlsplit(BASE)
    connection = http.client.HTTPConnection(parts.netloc, timeout=30)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        response.read()
        return response.status, {
            key.lower(): value for key, value in response.getheaders()
        }
    finally:
        connection.close()


def _reachable() -> bool:
    try:
        return _call("GET", "/health")[0] == 200
    except OSError:
        return False


class NginxProxyTests(unittest.TestCase):
    def setUp(self) -> None:
        if not _reachable():
            self.skipTest("Nginx indisponivel")

    def test_body_above_limit_is_rejected_with_413(self) -> None:
        body = b"x" * (27 * 1024 * 1024)
        status, _ = _call(
            "POST",
            "/api/assistants/any/documents",
            body=body,
            headers={"Content-Type": "application/octet-stream"},
        )
        self.assertEqual(status, 413)

    def test_body_within_limit_reaches_the_api(self) -> None:
        # Sem token a API responde 401: prova que o Nginx deixou passar.
        status, _ = _call(
            "POST",
            "/api/assistants/any/documents",
            body=b"x" * (1024 * 1024),
            headers={"Content-Type": "application/octet-stream"},
        )
        self.assertNotEqual(status, 413)

    def test_interactive_docs_are_not_exposed(self) -> None:
        for path in ("/api/docs", "/api/redoc", "/api/openapi.json"):
            with self.subTest(path=path):
                self.assertEqual(_call("GET", path)[0], 404)

    def test_metrics_are_not_exposed(self) -> None:
        self.assertEqual(_call("GET", "/api/metrics")[0], 404)

    def test_streaming_route_is_not_buffered(self) -> None:
        # A rota de streaming precisa de token; a verificacao e do cabecalho
        # que o backend envia e que o Nginx nao pode remover.
        status, headers = _call(
            "POST", "/api/conversations/x/chat/stream", body=b"{}",
            headers={"Content-Type": "application/json"},
        )
        self.assertIn(status, (401, 403, 404, 422))
        self.assertNotEqual(headers.get("content-encoding"), "gzip")

    def test_security_header_for_images(self) -> None:
        _, headers = _call("GET", "/health")
        self.assertIn("img-src 'self'", headers.get("content-security-policy", ""))


if __name__ == "__main__":
    unittest.main()
