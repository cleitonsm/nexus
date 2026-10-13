"""CT-46 (RNF-25): logs, rastreamentos e metricas sem token, chave nem texto.

Integra os adaptadores reais de observabilidade e o cliente HTTP do LLM:
``SpanTracer`` com o exportador OTLP/JSON, ``MetricsRegistry``, os logs em
JSON e ``HttpChatCompletionsLLM`` falando com um servidor HTTP local que
imita a API de chat (inclusive o streaming). O vector store, o reranker e os
repositorios sao os dubles dos testes unitarios. Nao exige Docker.

Uma pergunta passa pela rota sem streaming e pela de streaming, com o token do
usuario validado dentro de um trecho; depois, a saida inteira de logs, trechos
exportados e ``/metrics`` e varrida atras do token, da chave de API, do texto
integral do documento e da pergunta.
"""

from __future__ import annotations

import io
import json
import logging
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))

from access_doubles import AccessFixture  # noqa: E402
from chat_doubles import (  # noqa: E402
    ScriptedVectorStore,
    WordTokenCounter,
    build_retriever,
    hit,
)
from test_chat_flow import (  # noqa: E402
    ASSISTANT,
    CONVERSATION,
    GROUP,
    OWNER,
    InMemoryAssistantRepository,
    InMemoryConversationRepository,
)

from src.application.services import GroundedAnswerGenerator  # noqa: E402
from src.application.use_cases import (  # noqa: E402
    ChatWithAssistantInput,
    ChatWithAssistantUseCase,
)
from src.infrastructure.llm import HttpChatCompletionsLLM  # noqa: E402
from src.infrastructure.observability import (  # noqa: E402
    JsonLogFormatter,
    MetricsRegistry,
    OtlpJsonSpanExporter,
    SpanTracer,
    TracedLLMGateway,
    TracedTokenVerifier,
    bind_request_id,
    reset_request_id,
)

USER_TOKEN = "eyJhbGciOiJSUzI1NiJ9.ct46-token-do-usuario.assinatura"
API_KEY = "sk-ct46-chave-ficticia-0123456789"
DOCUMENT_TEXT = (
    "Clausula ficticia do CT-46: o reembolso de deslocamento corporativo "
    "segue a tabela interna Lambda-7 e exige aprovacao do gestor imediato."
)
QUESTION = "Qual a regra Lambda-7 para reembolso de deslocamento?"
ANSWER = "O reembolso exige aprovacao do gestor [1]."


class FakeChatCompletions(BaseHTTPRequestHandler):
    """Responde como a API de chat: JSON ou Server-Sent Events."""

    def log_message(self, *args) -> None:  # silencia o servidor de teste
        return None

    def do_POST(self) -> None:  # noqa: N802 - nome exigido pelo http.server
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        usage = {"prompt_tokens": 120, "completion_tokens": 12}
        if payload.get("stream"):
            parts = [{"choices": [{"delta": {"content": word + " "}}]} for word in ANSWER.split()]
            parts.append({"choices": [], "usage": usage})
            body = "".join(f"data: {json.dumps(part)}\n\n" for part in parts) + "data: [DONE]\n\n"
            self._reply(body.encode(), "text/event-stream")
            return
        message = {"choices": [{"message": {"content": ANSWER}}], "usage": usage}
        self._reply(json.dumps(message).encode(), "application/json")

    def _reply(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class AcceptingVerifier:
    def verify(self, token: str):
        if token != USER_TOKEN:
            raise ValueError("token desconhecido")
        return OWNER


class SensitiveDataLeakTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeChatCompletions)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.logs = io.StringIO()
        self._capture_logs()
        self.exported: list[bytes] = []
        self.exporter = OtlpJsonSpanExporter(
            endpoint="http://coletor.invalido:4318",
            service_name="nexus-backend",
            sender=lambda url, body, timeout: self.exported.append(body),
            start_thread=False,
        )
        self.metrics = MetricsRegistry()
        self.tracer = SpanTracer(exporter=self.exporter, metrics=self.metrics)

    def _capture_logs(self) -> None:
        handler = logging.StreamHandler(self.logs)
        handler.setFormatter(JsonLogFormatter())
        root = logging.getLogger()
        previous_level = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        self.addCleanup(root.removeHandler, handler)
        self.addCleanup(root.setLevel, previous_level)

    def _use_case(self) -> ChatWithAssistantUseCase:
        access = AccessFixture()
        access.link_assistant(ASSISTANT, GROUP)
        llm = TracedLLMGateway(
            HttpChatCompletionsLLM(
                api_url=f"http://127.0.0.1:{self.server.server_port}/v1/chat/completions",
                model="gpt-4o-mini",
                api_key=API_KEY,
            ),
            self.tracer,
            model="gpt-4o-mini",
        )
        return ChatWithAssistantUseCase(
            assistant_repository=InMemoryAssistantRepository(),
            conversation_repository=InMemoryConversationRepository(),
            context_retriever=build_retriever(
                ScriptedVectorStore([[hit("doc-ct46", DOCUMENT_TEXT, source_name="politica.pdf")]] * 2)
            ),
            answer_generator=GroundedAnswerGenerator(llm_gateway=llm),
            token_counter=WordTokenCounter(),
            access_control=access.control,
            tracer=self.tracer,
            metrics=self.metrics,
        )

    def _ask(self, *, stream: bool) -> str:
        data = ChatWithAssistantInput(user=OWNER, conversation_id=CONVERSATION, question=QUESTION)
        token = bind_request_id("4bf92f3577b34da6a3ce929d0e0e4736")
        try:
            with self.tracer.span("http.request", {"http.method": "POST"}):
                TracedTokenVerifier(AcceptingVerifier(), self.tracer).verify(USER_TOKEN)
                use_case = self._use_case()
                if stream:
                    events = list(use_case.start_stream(data))
                    return events[-1].result.assistant_message.content
                return use_case.execute(data).assistant_message.content
        finally:
            reset_request_id(token)

    def _everything_emitted(self) -> str:
        while self.exporter.flush():
            continue
        spans = "\n".join(body.decode("utf-8") for body in self.exported)
        return "\n".join([self.logs.getvalue(), spans, self.metrics.render()])

    def test_answers_come_from_the_http_client_in_both_routes(self) -> None:
        self.assertEqual(self._ask(stream=False), ANSWER)
        self.assertEqual(self._ask(stream=True), ANSWER)

    def test_no_token_key_document_text_or_question_leaves_the_process(self) -> None:
        self._ask(stream=False)
        self._ask(stream=True)
        emitted = self._everything_emitted()
        self.assertIn("llm.chat_completion", emitted, "os trechos deviam ter sido exportados")
        self.assertIn("chat.generate_answer", emitted)
        for name, secret in (
            ("token do usuario", USER_TOKEN),
            ("parte assinada do token", "ct46-token-do-usuario"),
            ("chave de API", API_KEY),
            ("texto integral do documento", DOCUMENT_TEXT),
            ("trecho do documento", "tabela interna Lambda-7"),
            ("pergunta", QUESTION),
        ):
            with self.subTest(name):
                self.assertNotIn(secret, emitted)

    def test_spans_keep_identifiers_and_counts(self) -> None:
        self._ask(stream=False)
        emitted = self._everything_emitted()
        self.assertIn(CONVERSATION, emitted)
        self.assertIn("4bf92f3577b34da6a3ce929d0e0e4736", emitted)
        self.assertIn('"llm.input_tokens"', emitted)


if __name__ == "__main__":
    unittest.main()
