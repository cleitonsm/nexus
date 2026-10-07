"""SPEC-20261007-001: logs estruturados (RF-27, RNF-25, RNF-29)."""

from __future__ import annotations

import io
import json
import logging
import unittest

from src.infrastructure.observability import (
    JsonLogFormatter,
    bind_request_id,
    configure_logging,
    get_request_id,
    normalize_request_id,
    reset_request_id,
)


def _record(message: str, **extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="nexus.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


class JsonLogFormatterTests(unittest.TestCase):
    def test_line_is_valid_json_with_request_id(self) -> None:
        token = bind_request_id("req-123")
        try:
            line = JsonLogFormatter().format(_record("chat.context.evaluated"))
        finally:
            reset_request_id(token)
        payload = json.loads(line)
        self.assertEqual(payload["event"], "chat.context.evaluated")
        self.assertEqual(payload["request_id"], "req-123")
        self.assertEqual(payload["level"], "INFO")
        self.assertIn("timestamp", payload)

    def test_request_id_is_null_outside_a_request(self) -> None:
        payload = json.loads(JsonLogFormatter().format(_record("worker.tick")))
        self.assertIsNone(payload["request_id"])

    def test_extra_fields_are_included(self) -> None:
        line = JsonLogFormatter().format(
            _record("llm.request.started", context_chunks=3, llm_model="gpt")
        )
        payload = json.loads(line)
        self.assertEqual(payload["context_chunks"], 3)
        self.assertEqual(payload["llm_model"], "gpt")

    def test_sensitive_fields_are_redacted(self) -> None:
        line = JsonLogFormatter().format(
            _record(
                "admin.saved",
                api_key="sk-secret",
                authorization="Bearer abc",
                access_token="abc",
                password="hunter2",
            )
        )
        self.assertNotIn("sk-secret", line)
        self.assertNotIn("Bearer abc", line)
        self.assertNotIn("hunter2", line)
        payload = json.loads(line)
        self.assertEqual(payload["api_key"], "[redacted]")

    def test_long_values_are_truncated(self) -> None:
        line = JsonLogFormatter().format(
            _record("ingest.failed", detail="x" * 5000)
        )
        payload = json.loads(line)
        self.assertLess(len(payload["detail"]), 400)
        self.assertTrue(payload["detail"].endswith("..."))

    def test_exception_is_reported_without_traceback_noise(self) -> None:
        try:
            raise RuntimeError("falha no provedor")
        except RuntimeError:
            import sys

            record = _record("llm.request.failed")
            record.exc_info = sys.exc_info()
        payload = json.loads(JsonLogFormatter().format(record))
        self.assertEqual(payload["error_type"], "RuntimeError")
        self.assertEqual(payload["error"], "falha no provedor")

    def test_non_serializable_values_do_not_break_the_line(self) -> None:
        line = JsonLogFormatter().format(_record("odd", value=object()))
        self.assertIsInstance(json.loads(line)["value"], str)


class RequestIdTests(unittest.TestCase):
    def test_bind_and_reset(self) -> None:
        self.assertIsNone(get_request_id())
        token = bind_request_id("abc")
        self.assertEqual(get_request_id(), "abc")
        reset_request_id(token)
        self.assertIsNone(get_request_id())

    def test_valid_incoming_id_is_kept(self) -> None:
        self.assertEqual(normalize_request_id("Req_123-abc"), "Req_123-abc")

    def test_missing_or_unsafe_incoming_id_is_replaced(self) -> None:
        for incoming in (None, "", "a b", "x" * 200, 'id"\n{"forged":1}'):
            generated = normalize_request_id(incoming)
            self.assertNotEqual(generated, incoming)
            self.assertRegex(generated, r"^[0-9a-f]{32}$")


class ConfigureLoggingTests(unittest.TestCase):
    def test_root_logger_emits_json_lines(self) -> None:
        stream = io.StringIO()
        root = logging.getLogger()
        previous_handlers = list(root.handlers)
        previous_level = root.level
        try:
            configure_logging(level="INFO", stream=stream)
            logging.getLogger("nexus.test").info(
                "evaluation.finished", extra={"items": 2}
            )
        finally:
            root.handlers = previous_handlers
            root.setLevel(previous_level)
        payload = json.loads(stream.getvalue().strip().splitlines()[-1])
        self.assertEqual(payload["event"], "evaluation.finished")
        self.assertEqual(payload["items"], 2)

    def test_server_loggers_are_routed_through_the_json_handler(self) -> None:
        stream = io.StringIO()
        plain = io.StringIO()
        root = logging.getLogger()
        previous_handlers = list(root.handlers)
        previous_level = root.level
        server = logging.getLogger("uvicorn.error")
        access = logging.getLogger("uvicorn.access")
        server.addHandler(logging.StreamHandler(plain))
        server.propagate = False
        access.addHandler(logging.StreamHandler(plain))
        try:
            configure_logging(level="INFO", stream=stream)
            server.info("Application startup complete.")
            access.info("GET /health 200")
        finally:
            root.handlers = previous_handlers
            root.setLevel(previous_level)
        lines = stream.getvalue().strip().splitlines()
        self.assertEqual(plain.getvalue(), "")
        self.assertEqual(len(lines), 1)
        self.assertEqual(
            json.loads(lines[0])["event"], "Application startup complete."
        )

    def test_configuring_twice_does_not_duplicate_handlers(self) -> None:
        stream = io.StringIO()
        root = logging.getLogger()
        previous_handlers = list(root.handlers)
        previous_level = root.level
        try:
            configure_logging(level="INFO", stream=stream)
            configure_logging(level="INFO", stream=stream)
            logging.getLogger("nexus.test").info("once")
        finally:
            root.handlers = previous_handlers
            root.setLevel(previous_level)
        self.assertEqual(len(stream.getvalue().strip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
