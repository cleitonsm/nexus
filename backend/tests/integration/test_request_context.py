"""SPEC-20261007-001, CT-05 (RF-27, RNF-29): identificador de requisicao."""

from __future__ import annotations

import io
import json
import logging
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware import REQUEST_ID_HEADER, register_request_context
from src.infrastructure.observability import configure_logging, get_request_id


def _build_app() -> FastAPI:
    app = FastAPI()
    register_request_context(app)

    @app.get("/ping")
    def ping() -> dict[str, str | None]:
        logging.getLogger("nexus.test").info("ping.handled")
        return {"request_id": get_request_id()}

    return app


class RequestContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stream = io.StringIO()
        root = logging.getLogger()
        self._handlers = list(root.handlers)
        self._level = root.level
        configure_logging(level="INFO", stream=self.stream)
        self.client = TestClient(_build_app())

    def tearDown(self) -> None:
        root = logging.getLogger()
        root.handlers = self._handlers
        root.setLevel(self._level)

    def _lines(self) -> list[dict[str, object]]:
        return [
            json.loads(line)
            for line in self.stream.getvalue().strip().splitlines()
        ]

    def test_generates_request_id_and_returns_it_in_the_header(self) -> None:
        response = self.client.get("/ping")
        request_id = response.headers[REQUEST_ID_HEADER]
        self.assertRegex(request_id, r"^[0-9a-f]{32}$")
        self.assertEqual(response.json()["request_id"], request_id)

    def test_keeps_a_safe_incoming_request_id(self) -> None:
        response = self.client.get("/ping", headers={REQUEST_ID_HEADER: "abc-123"})
        self.assertEqual(response.headers[REQUEST_ID_HEADER], "abc-123")

    def test_replaces_an_unsafe_incoming_request_id(self) -> None:
        response = self.client.get(
            "/ping",
            headers={REQUEST_ID_HEADER: "tem espaco e \"aspas\""},
        )
        self.assertRegex(response.headers[REQUEST_ID_HEADER], r"^[0-9a-f]{32}$")

    def test_every_log_line_of_a_request_is_json_with_the_same_id(self) -> None:
        response = self.client.get("/ping", headers={REQUEST_ID_HEADER: "req-1"})
        self.assertEqual(response.status_code, 200)
        lines = self._lines()
        events = [line["event"] for line in lines]
        self.assertIn("ping.handled", events)
        self.assertIn("http.request.finished", events)
        self.assertEqual({line["request_id"] for line in lines}, {"req-1"})

    def test_request_id_does_not_leak_between_requests(self) -> None:
        self.client.get("/ping", headers={REQUEST_ID_HEADER: "first"})
        second = self.client.get("/ping", headers={REQUEST_ID_HEADER: "second"})
        self.assertEqual(second.json()["request_id"], "second")
        self.assertIsNone(get_request_id())


if __name__ == "__main__":
    unittest.main()
