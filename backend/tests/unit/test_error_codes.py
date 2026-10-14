"""fix-14: corpo de erro unico ``{detail, code}``."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "src/api/error_codes.py"
_SPEC = importlib.util.spec_from_file_location("error_codes_under_test", _PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
error_body = _MODULE.error_body
error_code = _MODULE.error_code


class ErrorCodesTest(unittest.TestCase):
    def test_known_statuses_have_stable_codes(self) -> None:
        self.assertEqual(error_code(403), "forbidden")
        self.assertEqual(error_code(404), "not_found")
        self.assertEqual(error_code(503), "unavailable")

    def test_unknown_statuses_use_the_family(self) -> None:
        self.assertEqual(error_code(418), "client_error")
        self.assertEqual(error_code(504), "server_error")

    def test_body_keeps_detail_and_adds_code(self) -> None:
        self.assertEqual(
            error_body(404, "assistant not found"),
            {"detail": "assistant not found", "code": "not_found"},
        )

    def test_structured_detail_with_its_own_code_wins(self) -> None:
        detail = {"detail": "Limite", "code": "usage_limit", "window": "minute"}
        self.assertEqual(error_body(429, detail), detail)

    def test_structured_detail_without_code_is_kept_under_detail(self) -> None:
        body = error_body(409, {"document_id": "d1"})
        self.assertEqual(body["detail"], {"document_id": "d1"})
        self.assertEqual(body["code"], "conflict")


if __name__ == "__main__":
    unittest.main()
