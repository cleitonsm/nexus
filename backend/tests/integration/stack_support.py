"""Apoio dos testes que usam a pilha real do Compose (CT-50, CT-51, CT-52).

So biblioteca padrao. A API, o Keycloak e o LLM simulado sao acessados por
HTTP; sem a pilha, ``stack_available`` devolve falso e os testes sao pulados.

Variaveis: ``API_URL`` (padrao ``http://backend:8000``), ``KEYCLOAK_URL``
(padrao ``http://keycloak:8080``), ``KEYCLOAK_REALM`` (``nexus``),
``NEXUS_TEST_PASSWORD`` (``nexus-dev``, a senha dos usuarios do realm de
desenvolvimento). O cliente ``nexus-tests`` so existe nesse realm (V-D2).
"""

from __future__ import annotations

import http.client
import json
import os
import socket
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlencode, urlsplit

API_URL = os.getenv("API_URL", "http://backend:8000").rstrip("/")
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080").rstrip("/")
REALM = os.getenv("KEYCLOAK_REALM", "nexus")
TEST_PASSWORD = os.getenv("NEXUS_TEST_PASSWORD", "nexus-dev")


def call(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = 60.0,
) -> tuple[int, dict[str, str], bytes]:
    parts = urlsplit(url)
    connection = http.client.HTTPConnection(parts.netloc, timeout=timeout)
    try:
        target = parts.path + (f"?{parts.query}" if parts.query else "")
        connection.request(method, target, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = response.read()
        return (
            response.status,
            {key.lower(): value for key, value in response.getheaders()},
            payload,
        )
    finally:
        connection.close()


def stack_available() -> bool:
    try:
        return call("GET", f"{API_URL}/health", timeout=5)[0] == 200
    except OSError:
        return False


def token_for(username: str, password: str | None = None) -> str:
    form = urlencode(
        {
            "grant_type": "password",
            "client_id": os.getenv("KEYCLOAK_TESTS_CLIENT_ID", "nexus-tests"),
            "username": username,
            "password": password or TEST_PASSWORD,
        }
    )
    status, _, payload = call(
        "POST",
        f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=form.encode(),
    )
    if status != 200:
        raise RuntimeError(f"token request for {username} failed ({status}).")
    return json.loads(payload)["access_token"]


class Api:
    """Cliente minimo da API com um token fixo."""

    def __init__(self, token: str) -> None:
        self.token = token

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: object | None = None,
        raw: bytes | None = None,
        content_type: str | None = None,
        timeout: float = 120.0,
    ) -> tuple[int, dict[str, str], bytes]:
        headers = {"Authorization": f"Bearer {self.token}"}
        body = raw
        if payload is not None:
            body = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        if content_type:
            headers["Content-Type"] = content_type
        return call(
            method, f"{API_URL}{path}", headers=headers, body=body, timeout=timeout
        )

    def json(
        self, method: str, path: str, *, payload: object | None = None
    ) -> tuple[int, object]:
        status, _, body = self.request(method, path, payload=payload)
        try:
            return status, json.loads(body) if body else None
        except json.JSONDecodeError:
            return status, body.decode(errors="replace")

    def upload(
        self,
        assistant_id: str,
        name: str,
        content: bytes,
        groups: str | None = None,
        content_type: str = "text/markdown",
    ) -> tuple[int, object]:
        boundary = f"----nexus{uuid.uuid4().hex}"
        parts = [
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="{name}"\r\nContent-Type: {content_type}\r\n\r\n'.encode()
            + content
            + b"\r\n"
        ]
        if groups is not None:
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="groups"'
                f"\r\n\r\n{groups}\r\n".encode()
            )
        parts.append(f"--{boundary}--\r\n".encode())
        status, _, body = self.request(
            "POST",
            f"/assistants/{assistant_id}/documents",
            raw=b"".join(parts),
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        return status, json.loads(body) if body else None

    def wait_indexed(self, document_id: str, timeout: float = 300.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status, data = self.json("GET", f"/documents/{document_id}")
            if status == 200 and data["status"] in ("indexado", "falhou"):
                return data
            time.sleep(2)
        raise TimeoutError(f"document {document_id} did not finish indexing.")


class FakeLLMServer:
    """Servidor compativel com ``/chat/completions`` (sem streaming)."""

    def __init__(self, answer: str = "Resposta de teste [1].") -> None:
        self.answer = answer
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - API do http.server
                length = int(self.headers.get("Content-Length", "0"))
                outer.requests.append(json.loads(self.rfile.read(length) or b"{}"))
                body = json.dumps(
                    {
                        "choices": [{"message": {"content": outer.answer}}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("0.0.0.0", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        """Endereco alcancavel pelos outros containers do Compose."""
        host = os.getenv("FAKE_LLM_HOST") or socket.gethostname()
        return f"http://{host}:{self._server.server_address[1]}/v1/chat/completions"

    def __enter__(self) -> "FakeLLMServer":
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
