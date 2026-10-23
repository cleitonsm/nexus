"""SPEC-009: nova tentativa nas chamadas ao LLM (CT-71 a CT-73).

Usa um servidor HTTP local que responde um roteiro de respostas, para exercitar
o cliente real (urllib) sem rede nem provedor.
"""

from __future__ import annotations

import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.infrastructure.llm import HttpChatCompletionsLLM, LLMProviderError

OK_BODY = json.dumps(
    {
        "choices": [{"message": {"content": "Resposta [1]"}}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 3},
    }
).encode("utf-8")
STREAM_BODY = (
    b'data: {"choices":[{"delta":{"content":"Ola"}}]}\n\n'
    b'data: {"choices":[],"usage":{"prompt_tokens":5,"completion_tokens":1}}\n\n'
    b"data: [DONE]\n\n"
)


class ScriptedServer:
    """Responde, em ordem, o roteiro ``(status, corpo)``; ``None`` derruba a conexao."""

    def __init__(self, script: list[tuple[int, bytes] | None]) -> None:
        self.script = list(script)
        self.requests = 0
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(length)
                outer.requests += 1
                step = outer.script.pop(0) if outer.script else (500, b"fim do roteiro")
                if step is None:
                    self.connection.close()
                    return
                status, body = step
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}/v1/chat/completions"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> ScriptedServer:
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._server.shutdown()
        self._server.server_close()


class LLMRetryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.sleeps: list[float] = []

    def llm(self, server: ScriptedServer) -> HttpChatCompletionsLLM:
        return HttpChatCompletionsLLM(
            api_url=server.url,
            model="gemini-flash",
            api_key="chave-de-teste",
            timeout_seconds=5.0,
            sleep=self.sleeps.append,
        )

    def ask(self, llm: HttpChatCompletionsLLM) -> str:
        return llm.generate_with_usage(
            prompt="Pergunta", context_chunks=[], conversation_history=[]
        ).text

    def test_retries_a_transient_503_and_delivers_the_next_answer(self) -> None:
        """CT-71"""
        with ScriptedServer([(503, b"high demand"), (200, OK_BODY)]) as server:
            self.assertEqual(self.ask(self.llm(server)), "Resposta [1]")
            self.assertEqual(server.requests, 2)
        self.assertEqual(self.sleeps, [1.0])

    def test_retries_429_and_waits_one_then_three_seconds(self) -> None:
        """CT-71"""
        script = [(429, b"slow down"), (502, b"bad gateway"), (200, OK_BODY)]
        with ScriptedServer(script) as server:
            self.assertEqual(self.ask(self.llm(server)), "Resposta [1]")
            self.assertEqual(server.requests, 3)
        self.assertEqual(self.sleeps, [1.0, 3.0])

    def test_retries_a_dropped_connection(self) -> None:
        """CT-71"""
        with ScriptedServer([None, (200, OK_BODY)]) as server:
            self.assertEqual(self.ask(self.llm(server)), "Resposta [1]")
            self.assertEqual(server.requests, 2)

    def test_request_errors_are_not_retried(self) -> None:
        """CT-72"""
        for status in (400, 401, 403, 404):
            with self.subTest(status=status):
                self.sleeps.clear()
                with ScriptedServer([(status, b"recusado"), (200, OK_BODY)]) as server:
                    with self.assertRaises(LLMProviderError) as raised:
                        self.ask(self.llm(server))
                    self.assertEqual(server.requests, 1)
                self.assertIn(f"rejected request: {status}", str(raised.exception))
                self.assertEqual(self.sleeps, [])

    def test_gives_up_after_three_attempts_with_the_current_error(self) -> None:
        """CT-72"""
        with ScriptedServer([(503, b"a"), (503, b"b"), (503, b"c"), (200, OK_BODY)]) as server:
            with self.assertRaises(LLMProviderError) as raised:
                self.ask(self.llm(server))
            self.assertEqual(server.requests, 3)
        self.assertIn("rejected request: 503 c", str(raised.exception))
        self.assertEqual(self.sleeps, [1.0, 3.0])

    def test_unreachable_provider_gives_up_after_three_attempts(self) -> None:
        """CT-72"""
        llm = HttpChatCompletionsLLM(
            api_url="http://127.0.0.1:1/v1/chat/completions",
            model="m",
            api_key="k",
            timeout_seconds=2.0,
            sleep=self.sleeps.append,
        )
        with self.assertRaises(LLMProviderError) as raised:
            self.ask(llm)
        self.assertIn("unreachable", str(raised.exception))
        self.assertEqual(self.sleeps, [1.0, 3.0])

    def test_retry_delays_are_configurable_and_empty_means_no_retry(self) -> None:
        """CT-72"""
        with ScriptedServer([(503, b"x"), (200, OK_BODY)]) as server:
            llm = HttpChatCompletionsLLM(
                api_url=server.url,
                model="m",
                api_key="k",
                retry_delays=(),
                sleep=self.sleeps.append,
            )
            with self.assertRaises(LLMProviderError):
                self.ask(llm)
            self.assertEqual(server.requests, 1)

    def test_stream_retries_only_opening_the_connection(self) -> None:
        """CT-73"""
        with ScriptedServer([(503, b"high demand"), (200, STREAM_BODY)]) as server:
            chunks = list(
                self.llm(server).generate_stream(
                    prompt="Pergunta", context_chunks=[], conversation_history=[]
                )
            )
            self.assertEqual("".join(chunk.text for chunk in chunks), "Ola")
            self.assertEqual(server.requests, 2)
        self.assertEqual(self.sleeps, [1.0])

    def test_stream_does_not_repeat_after_the_provider_answered(self) -> None:
        """CT-73: depois dos cabecalhos 200 nao ha nova requisicao."""
        with ScriptedServer([(200, STREAM_BODY), (200, STREAM_BODY)]) as server:
            chunks = list(
                self.llm(server).generate_stream(
                    prompt="Pergunta", context_chunks=[], conversation_history=[]
                )
            )
            self.assertEqual(server.requests, 1)
        self.assertEqual(sum(1 for chunk in chunks if chunk.text), 1)
        self.assertEqual(self.sleeps, [])


class SlowServer:
    """Aceita a conexao e demora a responder: tempo esgotado na leitura."""

    def __init__(self, delay: float) -> None:
        self.requests = 0
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(length)
                outer.requests += 1
                time.sleep(delay)
                try:
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(OK_BODY)))
                    self.end_headers()
                    self.wfile.write(OK_BODY)
                except OSError:
                    pass

            def log_message(self, *_: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}/v1/chat/completions"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "SlowServer":
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._server.shutdown()
        self._server.server_close()


class LLMTimeoutTestCase(unittest.TestCase):
    """V6 da rc6 (2026-10-21): o TimeoutError escapava cru do cliente."""

    def test_read_timeout_becomes_provider_error_without_retry(self) -> None:
        sleeps: list[float] = []
        with SlowServer(delay=1.0) as server:
            llm = HttpChatCompletionsLLM(
                api_url=server.url,
                model="gemini-flash",
                api_key="chave-de-teste",
                timeout_seconds=0.2,
                sleep=sleeps.append,
            )
            with self.assertRaises(LLMProviderError) as caught:
                llm.generate_with_usage(prompt="P", context_chunks=[], conversation_history=[])
            self.assertIn("timed out", str(caught.exception))
            self.assertEqual(server.requests, 1)  # D2: nao repete
        self.assertEqual(sleeps, [])
        # LLMProviderError e RuntimeError: o fallback da reescrita (grounded_answer) o trata.
        self.assertIsInstance(caught.exception, RuntimeError)


if __name__ == "__main__":
    unittest.main()
