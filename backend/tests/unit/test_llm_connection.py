"""SPEC-008: provedor, modelo e URL do LLM na administracao (CT-63 a CT-67)."""

from __future__ import annotations

import unittest

from access_doubles import AccessFixture, admin, curator, make_user

from src.application.use_cases import (
    GetLLMConnectionUseCase,
    UpdateLLMConnectionInput,
    UpdateLLMConnectionUseCase,
    resolve_llm_connection,
)
from src.domain import (
    PROVIDER_ENDPOINTS,
    AccessDeniedError,
    AuditAction,
    DomainValidationError,
    LLMConnection,
    LLMProvider,
    provider_for_url,
)

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
ENVIRONMENT = LLMConnection.from_environment(model="gpt-4o-mini", api_url=OPENAI_URL)


class InMemoryLLMConnections:
    def __init__(self, connection: LLMConnection | None = None) -> None:
        self.connection = connection
        self.updated_by: str | None = None

    def get(self) -> LLMConnection | None:
        return self.connection

    def save(self, connection: LLMConnection, *, updated_by: str) -> LLMConnection:
        self.connection = connection
        self.updated_by = updated_by
        return connection


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


class LLMConnectionUseCasesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.access = AccessFixture()
        self.repository = InMemoryLLMConnections()

    def update(self, **overrides: object):
        values: dict[str, object] = {
            "user": admin(),
            "provider": "gemini",
            "model": "gemini-flash",
        }
        values.update(overrides)
        return UpdateLLMConnectionUseCase(
            repository=self.repository,
            access_control=self.access.control,
            default=ENVIRONMENT,
        ).execute(UpdateLLMConnectionInput(**values))  # type: ignore[arg-type]

    def get(self, user):
        return GetLLMConnectionUseCase(
            repository=self.repository,
            access_control=self.access.control,
            default=ENVIRONMENT,
        ).execute(user)

    def test_without_stored_value_the_environment_is_the_effective_value(self) -> None:
        """CT-64"""
        result = self.get(admin())
        self.assertEqual(
            (result.provider, result.model, result.api_url, result.source),
            ("openai", "gpt-4o-mini", OPENAI_URL, "ambiente"),
        )
        self.assertIs(resolve_llm_connection(self.repository, ENVIRONMENT), ENVIRONMENT)

    def test_stored_value_wins_over_the_environment(self) -> None:
        """CT-64 e CT-66"""
        saved = self.update()
        self.assertEqual(
            (saved.provider, saved.model, saved.api_url, saved.source),
            ("gemini", "gemini-flash", GEMINI_URL, "configurado"),
        )
        effective = resolve_llm_connection(self.repository, ENVIRONMENT)
        self.assertEqual((effective.provider, effective.model), (LLMProvider.GEMINI, "gemini-flash"))
        self.assertEqual(self.get(admin()).source, "configurado")
        self.assertEqual(self.repository.updated_by, "admin-1")

    def test_only_the_administrator_reads_or_changes(self) -> None:
        """CT-65"""
        for user in (curator(), make_user("u-1")):
            with self.subTest(user=user.id):
                with self.assertRaises(AccessDeniedError):
                    self.get(user)
                with self.assertRaises(AccessDeniedError):
                    self.update(user=user)
        self.assertIsNone(self.repository.connection)
        self.assertIn(AuditAction.ACCESS_DENIED, self.access.audit.actions())

    def test_change_is_audited_with_previous_and_new_values_and_no_key(self) -> None:
        """CT-66"""
        self.update()
        event = self.access.audit.last(AuditAction.LLM_SETTINGS_CHANGED)
        self.assertEqual(event.details["previous_provider"], "openai")
        self.assertEqual(event.details["previous_model"], "gpt-4o-mini")
        self.assertEqual(event.details["provider"], "gemini")
        self.assertEqual(event.details["model"], "gemini-flash")
        self.assertEqual(event.details["api_url"], GEMINI_URL)
        self.assertFalse([key for key in event.details if "key" in key.lower()])

    def test_second_change_records_the_stored_value_as_previous(self) -> None:
        self.update()
        self.update(provider="openai", model="gpt-4o")
        event = self.access.audit.last(AuditAction.LLM_SETTINGS_CHANGED)
        self.assertEqual(event.details["previous_provider"], "gemini")
        self.assertEqual(event.details["previous_model"], "gemini-flash")

    def test_invalid_input_keeps_the_previous_value_and_writes_no_audit(self) -> None:
        self.update()
        with self.assertRaises(DomainValidationError):
            self.update(provider="custom", model="x", api_url="http://inseguro.example.com")
        self.assertEqual(self.repository.connection.model, "gemini-flash")
        self.assertEqual(self.access.audit.actions().count("llm_settings.changed"), 1)

    def test_local_environment_allows_http_urls(self) -> None:
        url = "http://host.docker.internal:11434/v1/chat/completions"
        saved = UpdateLLMConnectionUseCase(
            repository=self.repository,
            access_control=self.access.control,
            default=ENVIRONMENT,
            allow_insecure_http=True,
        ).execute(
            UpdateLLMConnectionInput(
                user=admin(), provider="custom", model="llama3", api_url=url
            )
        )
        self.assertEqual(saved.api_url, url)


if __name__ == "__main__":
    unittest.main()
