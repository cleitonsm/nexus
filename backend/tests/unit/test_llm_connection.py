"""SPEC-008 (regras de provedor, modelo e URL, CT-63 e CT-67), reaproveitadas pelas
credenciais da SPEC-013; os casos de uso da SPEC-008 sairam com a D9."""

from __future__ import annotations

import unittest

from src.domain import (
    PROVIDER_ENDPOINTS,
    DomainValidationError,
    LLMConnection,
    LLMProvider,
    provider_for_url,
)

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
ENVIRONMENT = LLMConnection.from_environment(model="gpt-4o-mini", api_url=OPENAI_URL)


class LLMConnectionBuildTestCase(unittest.TestCase):
    """CT-63 e CT-67: o que o administrador pode informar."""

    def build(self, **overrides: object) -> LLMConnection:
        values: dict[str, object] = {
            "provider": "custom",
            "model": "meu-modelo",
            "api_url": "https://llm.example.com/v1/chat/completions",
        }
        values.update(overrides)
        return LLMConnection.build(**values)  # type: ignore[arg-type]

    def test_presets_use_the_provider_url_and_ignore_the_one_sent(self) -> None:
        gemini = self.build(provider="gemini", api_url="https://evil.example.com/x")
        self.assertEqual(gemini.provider, LLMProvider.GEMINI)
        self.assertEqual(gemini.api_url, PROVIDER_ENDPOINTS[LLMProvider.GEMINI])
        self.assertEqual(self.build(provider="openai", api_url=None).api_url, OPENAI_URL)

    def test_custom_provider_keeps_the_url_and_trims_the_model(self) -> None:
        connection = self.build(model="  llama-3  ")
        self.assertEqual(connection.provider, LLMProvider.CUSTOM)
        self.assertEqual(connection.model, "llama-3")
        self.assertEqual(connection.api_url, "https://llm.example.com/v1/chat/completions")

    def test_invalid_models_are_rejected(self) -> None:
        for model in ("", "   ", "dois nomes", "tab\tmodelo", "m" * 201):
            with self.subTest(model=model), self.assertRaises(DomainValidationError):
                self.build(model=model)

    def test_unknown_provider_is_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.build(provider="outro")

    def test_unsafe_custom_urls_are_rejected(self) -> None:
        urls = (
            None,
            "",
            "ftp://llm.example.com/v1",
            "http://llm.example.com/v1",
            "https://usuario:senha@llm.example.com/v1",
            "https://usuario@llm.example.com/v1",
            "https://llm.example.com/v1?key=segredo",
            "https://llm.example.com/v1#frag",
            "https:///sem-host",
            "https://llm example.com/v1",
            "https://llm.example.com:abc/v1",
        )
        for url in urls:
            with self.subTest(url=url), self.assertRaises(DomainValidationError):
                self.build(api_url=url)

    def test_http_is_accepted_only_in_the_local_environment(self) -> None:
        url = "http://host.docker.internal:11434/v1/chat/completions"
        with self.assertRaises(DomainValidationError):
            self.build(api_url=url)
        self.assertEqual(self.build(api_url=url, allow_insecure_http=True).api_url, url)

    def test_provider_is_inferred_from_the_environment_url(self) -> None:
        self.assertEqual(provider_for_url(OPENAI_URL), LLMProvider.OPENAI)
        self.assertEqual(provider_for_url(GEMINI_URL + " "), LLMProvider.GEMINI)
        self.assertEqual(provider_for_url("https://x.example.com/v1"), LLMProvider.CUSTOM)


if __name__ == "__main__":
    unittest.main()
