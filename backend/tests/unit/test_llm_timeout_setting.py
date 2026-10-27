"""SPEC-20261026-012 D14: tempo limite configuravel das chamadas ao LLM."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.infrastructure.composition import (
    DEFAULT_LLM_TIMEOUT_SECONDS,
    llm_timeout_seconds,
)


class LLMTimeoutSettingTestCase(unittest.TestCase):
    def test_default_keeps_thirty_seconds(self) -> None:
        with patch.dict(os.environ, {"LLM_TIMEOUT_SECONDS": ""}):
            self.assertEqual(llm_timeout_seconds(), DEFAULT_LLM_TIMEOUT_SECONDS)
        self.assertEqual(DEFAULT_LLM_TIMEOUT_SECONDS, 30.0)

    def test_value_from_the_environment(self) -> None:
        with patch.dict(os.environ, {"LLM_TIMEOUT_SECONDS": "120"}):
            self.assertEqual(llm_timeout_seconds(), 120.0)

    def test_invalid_values_are_rejected(self) -> None:
        for raw in ("0", "-5", "abc"):
            with self.subTest(raw=raw), patch.dict(os.environ, {"LLM_TIMEOUT_SECONDS": raw}):
                with self.assertRaises(ValueError):
                    llm_timeout_seconds()


if __name__ == "__main__":
    unittest.main()
