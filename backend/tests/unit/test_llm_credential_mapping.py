"""SPEC-013: colunas JSON das credenciais e do perfil do assistente (parte unitaria do CT-107)."""

from __future__ import annotations

import unittest
from decimal import Decimal

from src.domain import (
    PROVIDER_ENDPOINTS,
    DomainValidationError,
    LLMModelOption,
    LLMProvider,
    RetrievalProfile,
)
from src.infrastructure.llm_credential_mapping import (
    credential_from_row,
    models_from_json,
    models_to_json,
    profile_from_json,
    profile_to_json,
)

OPENAI_URL = PROVIDER_ENDPOINTS[LLMProvider.OPENAI]


def row(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "credential_id": "cred-1",
        "name": "OpenAI",
        "provider": "openai",
        "api_url": OPENAI_URL,
        "models": [{"name": "gpt-4o-mini", "input_per_1k": None, "output_per_1k": None}],
        "default_model": "gpt-4o-mini",
        "is_default": True,
        "encrypted_key": "cifrado",
    }
    values.update(overrides)
    return values


class ModelsJsonTestCase(unittest.TestCase):
    def test_prices_round_trip_as_text_without_losing_digits(self) -> None:
        models = (
            LLMModelOption(name="gpt-4o-mini"),
            LLMModelOption(
                name="gpt-4o",
                input_per_1k=Decimal("0.00015"),
                output_per_1k=Decimal("0.0006"),
            ),
        )
        stored = models_to_json(models)
        self.assertEqual(stored[1]["input_per_1k"], "0.00015")
        self.assertIsNone(stored[0]["output_per_1k"])
        self.assertEqual(models_from_json(stored), models)

    def test_missing_price_keys_mean_no_price(self) -> None:
        self.assertEqual(models_from_json([{"name": "m"}]), (LLMModelOption(name="m"),))

    def test_invalid_json_is_rejected(self) -> None:
        for raw in ({"name": "m"}, [{"preco": 1}], [{"name": "m", "input_per_1k": "x", "output_per_1k": "1"}]):
            with self.subTest(raw=raw), self.assertRaises(DomainValidationError):
                models_from_json(raw)


class CredentialFromRowTestCase(unittest.TestCase):
    def test_valid_row(self) -> None:
        credential = credential_from_row(**row())
        self.assertIsNotNone(credential)
        self.assertTrue(credential.is_default)
        self.assertTrue(credential.key_configured)
        self.assertEqual(credential.provider, LLMProvider.OPENAI)

    def test_key_configured_follows_the_ciphertext(self) -> None:
        self.assertFalse(credential_from_row(**row(encrypted_key=None)).key_configured)
        self.assertFalse(credential_from_row(**row(encrypted_key="")).key_configured)

    def test_invalid_rows_are_skipped_with_a_warning(self) -> None:
        cases = (
            row(provider="azure"),
            row(api_url="https://api.openai.com/v1/chat/completions?key=segredo"),
            row(models=[]),
            row(default_model="gpt-5"),
            row(models="nao-e-lista"),
        )
        for values in cases:
            with self.subTest(values=values), self.assertLogs(
                "src.infrastructure.llm_credential_mapping", "WARNING"
            ) as logs:
                self.assertIsNone(credential_from_row(**values))
            # RN-39: o aviso leva o id, nunca a URL nem o ciphertext.
            self.assertNotIn("segredo", "".join(logs.output))
            self.assertNotIn("cifrado", "".join(logs.output))


class ProfileJsonTestCase(unittest.TestCase):
    def test_round_trip(self) -> None:
        profile = RetrievalProfile(hybrid_enabled=False, candidates=40, top_k=8, min_score=0.3)
        self.assertEqual(profile_from_json(profile_to_json(profile), assistant_id="a"), profile)

    def test_empty_profile_is_stored_as_null(self) -> None:
        self.assertIsNone(profile_to_json(RetrievalProfile()))
        self.assertEqual(profile_from_json(None, assistant_id="a"), RetrievalProfile())

    def test_invalid_stored_profile_falls_back_to_empty(self) -> None:
        for raw in ({"top_k": 99}, {"rerank": False}, ["x"]):
            with self.subTest(raw=raw), self.assertLogs(
                "src.infrastructure.llm_credential_mapping", "WARNING"
            ):
                self.assertEqual(profile_from_json(raw, assistant_id="a"), RetrievalProfile())


if __name__ == "__main__":
    unittest.main()
