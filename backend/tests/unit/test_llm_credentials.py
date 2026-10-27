"""SPEC-013: credenciais de LLM no dominio (CT-99, CT-101, CT-102)."""

from __future__ import annotations

import unittest
from decimal import Decimal

from src.domain import (
    PROVIDER_ENDPOINTS,
    Assistant,
    AssistantId,
    AssistantName,
    AuditAction,
    DomainValidationError,
    LLMCredential,
    LLMCredentialId,
    LLMCredentialInUseError,
    LLMModelOption,
    LLMProvider,
    RetrievalProfile,
    assistants_falling_back,
    assistants_following_default,
    assistants_using,
    default_after_change,
    default_for_new,
    ensure_models_removable,
    ensure_removable,
    ensure_single_default,
)

OPENAI_URL = PROVIDER_ENDPOINTS[LLMProvider.OPENAI]
GEMINI_URL = PROVIDER_ENDPOINTS[LLMProvider.GEMINI]


def credential(
    credential_id: str = "cred-openai",
    *,
    name: str = "OpenAI",
    models: tuple[str, ...] = ("gpt-4o-mini", "gpt-4o"),
    default_model: str = "gpt-4o-mini",
    is_default: bool = False,
    provider: LLMProvider = LLMProvider.OPENAI,
) -> LLMCredential:
    return LLMCredential(
        id=LLMCredentialId(credential_id),
        name=name,
        provider=provider,
        api_url=PROVIDER_ENDPOINTS.get(provider, "https://llm.exemplo.com/v1/chat"),
        models=tuple(LLMModelOption(name=model) for model in models),
        default_model=default_model,
        is_default=is_default,
        key_configured=True,
    )


def assistant(
    assistant_id: str,
    *,
    credential_id: str | None = None,
    model: str | None = None,
) -> Assistant:
    return Assistant(
        id=AssistantId(assistant_id),
        name=AssistantName(f"Assistente {assistant_id}"),
        llm_credential_id=LLMCredentialId(credential_id) if credential_id else None,
        llm_model=model,
    )


class LLMModelOptionTestCase(unittest.TestCase):
    """CT-99 (D8, T1): nome do modelo e preco opcional."""

    def test_model_without_price(self) -> None:
        option = LLMModelOption(name=" gpt-4o-mini ")
        self.assertEqual(option.name, "gpt-4o-mini")
        self.assertFalse(option.has_price)
        self.assertIsNone(option.pricing("USD"))

    def test_model_with_price_builds_pricing_in_the_given_currency(self) -> None:
        option = LLMModelOption(
            name="gpt-4o",
            input_per_1k=Decimal("0.0025"),
            output_per_1k=Decimal("0.01"),
        )
        pricing = option.pricing("USD")
        self.assertIsNotNone(pricing)
        self.assertEqual(pricing.input_per_1k, Decimal("0.0025"))
        self.assertEqual(pricing.output_per_1k, Decimal("0.01"))
        self.assertEqual(pricing.currency, "USD")

    def test_zero_price_is_a_price(self) -> None:
        option = LLMModelOption(
            name="local", input_per_1k=Decimal("0"), output_per_1k=Decimal("0")
        )
        self.assertTrue(option.has_price)

    def test_only_one_price_is_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            LLMModelOption(name="gpt-4o", input_per_1k=Decimal("0.01"))
        with self.assertRaises(DomainValidationError):
            LLMModelOption(name="gpt-4o", output_per_1k=Decimal("0.01"))

    def test_negative_price_is_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            LLMModelOption(
                name="gpt-4o",
                input_per_1k=Decimal("-0.01"),
                output_per_1k=Decimal("0.01"),
            )

    def test_invalid_model_names_are_rejected(self) -> None:
        for name in ("", "   ", "gpt 4o", "x" * 201):
            with self.subTest(name=name), self.assertRaises(DomainValidationError):
                LLMModelOption(name=name)


class LLMCredentialTestCase(unittest.TestCase):
    """CT-99: nome, URL, modelos e modelo padrao."""

    def build(self, **overrides: object) -> LLMCredential:
        values: dict[str, object] = {
            "credential_id": "cred-1",
            "name": "Gemini do juridico",
            "provider": "gemini",
            "api_url": None,
            "models": (LLMModelOption(name="gemini-3.8-flash"),),
            "default_model": "gemini-3.8-flash",
        }
        values.update(overrides)
        return LLMCredential.build(**values)  # type: ignore[arg-type]

    def test_preset_fixes_the_provider_url(self) -> None:
        built = self.build(api_url="https://outro.exemplo.com/v1/chat")
        self.assertEqual(built.provider, LLMProvider.GEMINI)
        self.assertEqual(built.api_url, GEMINI_URL)
        self.assertEqual(built.id, LLMCredentialId("cred-1"))
        self.assertFalse(built.is_default)
        self.assertFalse(built.key_configured)

    def test_custom_provider_keeps_a_valid_https_url(self) -> None:
        built = self.build(provider="custom", api_url="https://llm.exemplo.com/v1/chat")
        self.assertEqual(built.provider, LLMProvider.CUSTOM)
        self.assertEqual(built.api_url, "https://llm.exemplo.com/v1/chat")

    def test_custom_provider_follows_the_url_rules_of_spec_008(self) -> None:
        for url in (
            "http://llm.exemplo.com/v1/chat",
            "https://usuario:senha@llm.exemplo.com/v1/chat",
            "https://llm.exemplo.com/v1/chat?key=abc",
            "https://llm.exemplo.com/v1/chat#x",
            "",
        ):
            with self.subTest(url=url), self.assertRaises(DomainValidationError):
                self.build(provider="custom", api_url=url)

    def test_http_only_when_allowed(self) -> None:
        built = self.build(
            provider="custom",
            api_url="http://localhost:11434/v1/chat/completions",
            allow_insecure_http=True,
        )
        self.assertTrue(built.api_url.startswith("http://"))

    def test_unknown_provider_is_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.build(provider="azure")

    def test_name_is_trimmed_and_limited(self) -> None:
        self.assertEqual(self.build(name="  Chave A  ").name, "Chave A")
        self.assertEqual(len(self.build(name="n" * 100).name), 100)
        for name in ("", "   ", "n" * 101, "linha\nquebrada"):
            with self.subTest(name=name), self.assertRaises(DomainValidationError):
                self.build(name=name)

    def test_needs_at_least_one_model(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.build(models=())

    def test_duplicate_models_are_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.build(
                models=(
                    LLMModelOption(name="gemini-3.8-flash"),
                    LLMModelOption(name="gemini-3.8-flash"),
                )
            )

    def test_default_model_must_be_in_the_list(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.build(default_model="gemini-pro")

    def test_model_lookup_uses_the_default_when_none(self) -> None:
        built = credential()
        self.assertEqual(built.model(None).name, "gpt-4o-mini")
        self.assertEqual(built.model("gpt-4o").name, "gpt-4o")
        self.assertEqual(built.model_names, ("gpt-4o-mini", "gpt-4o"))
        with self.assertRaises(DomainValidationError):
            built.model("gpt-5")

    def test_connection_for_feeds_the_existing_http_client(self) -> None:
        connection = credential().connection_for("gpt-4o")
        self.assertEqual(connection.provider, LLMProvider.OPENAI)
        self.assertEqual(connection.api_url, OPENAI_URL)
        self.assertEqual(connection.model, "gpt-4o")
        self.assertEqual(credential().connection_for(None).model, "gpt-4o-mini")

    def test_direct_construction_rejects_urls_that_could_carry_a_secret(self) -> None:
        # RN-39: repositorio e migracao constroem sem passar por ``build``.
        for url in (
            "https://usuario:senha@llm.exemplo.com/v1/chat",
            "https://llm.exemplo.com/v1/chat?key=abc",
            "https://llm.exemplo.com/v1/chat#abc",
            "   ",
        ):
            with self.subTest(url=url), self.assertRaises(DomainValidationError):
                LLMCredential(
                    id=LLMCredentialId("c"),
                    name="Personalizada",
                    provider=LLMProvider.CUSTOM,
                    api_url=url,
                    models=(LLMModelOption(name="m"),),
                    default_model="m",
                )

    def test_preset_must_point_to_its_endpoint(self) -> None:
        with self.assertRaises(DomainValidationError):
            LLMCredential(
                id=LLMCredentialId("c"),
                name="OpenAI",
                provider=LLMProvider.OPENAI,
                api_url="https://outro.exemplo.com/v1/chat",
                models=(LLMModelOption(name="gpt-4o"),),
                default_model="gpt-4o",
            )

    def test_repr_never_carries_a_key(self) -> None:
        # RN-39: a entidade nao tem campo de chave, so o indicador.
        built = credential()
        self.assertNotIn("key=", repr(built).replace("key_configured=", ""))
        self.assertFalse(hasattr(built, "api_key"))


class ModelFallbackTestCase(unittest.TestCase):
    """D11: recuo ao modelo padrao da credencial padrao."""

    def test_known_model_is_used_without_fallback(self) -> None:
        option, fell_back = credential().model_with_fallback("gpt-4o")
        self.assertEqual((option.name, fell_back), ("gpt-4o", False))

    def test_no_model_uses_the_default_without_fallback(self) -> None:
        option, fell_back = credential().model_with_fallback(None)
        self.assertEqual((option.name, fell_back), ("gpt-4o-mini", False))

    def test_missing_model_falls_back_to_the_default(self) -> None:
        gemini = credential(
            "cred-gemini",
            name="Gemini",
            provider=LLMProvider.GEMINI,
            models=("gemini-3.8-flash",),
            default_model="gemini-3.8-flash",
        )
        option, fell_back = gemini.model_with_fallback("gpt-4o")
        self.assertEqual((option.name, fell_back), ("gemini-3.8-flash", True))

    def test_assistants_falling_back_lists_only_followers_with_a_missing_model(self) -> None:
        gemini = credential(
            "cred-gemini",
            name="Gemini",
            provider=LLMProvider.GEMINI,
            models=("gemini-3.8-flash",),
            default_model="gemini-3.8-flash",
        )
        assistants = [
            assistant("rh", model="gpt-4o"),
            assistant("financeiro"),
            assistant("compras", model="gemini-3.8-flash"),
            assistant("juridico", credential_id="cred-openai", model="gpt-4o"),
        ]
        self.assertEqual(
            [item.value for item in assistants_falling_back(gemini, assistants)],
            ["rh"],
        )


class DefaultCredentialTestCase(unittest.TestCase):
    """CT-101 (RN-37): no maximo uma padrao; havendo credencial, exatamente uma."""

    def test_first_credential_becomes_default(self) -> None:
        self.assertTrue(default_for_new([], requested=False))
        self.assertTrue(default_for_new([credential(is_default=True)], requested=True))
        self.assertFalse(default_for_new([credential(is_default=True)], requested=False))

    def test_marking_another_unmarks_the_previous(self) -> None:
        openai = credential("cred-openai", is_default=True)
        gemini = credential(
            "cred-gemini",
            name="Gemini",
            provider=LLMProvider.GEMINI,
            models=("gemini-3.8-flash",),
            default_model="gemini-3.8-flash",
        )
        updated = default_after_change([openai, gemini], LLMCredentialId("cred-gemini"))
        defaults = {item.id.value: item.is_default for item in updated}
        self.assertEqual(defaults, {"cred-openai": False, "cred-gemini": True})
        ensure_single_default(updated)

    def test_marking_an_unknown_credential_fails(self) -> None:
        with self.assertRaises(DomainValidationError):
            default_after_change([credential(is_default=True)], LLMCredentialId("nada"))

    def test_single_default_invariant(self) -> None:
        ensure_single_default([])
        ensure_single_default([credential(is_default=True)])
        with self.assertRaises(DomainValidationError):
            ensure_single_default([credential(is_default=False)])
        with self.assertRaises(DomainValidationError):
            ensure_single_default(
                [
                    credential("a", name="A", is_default=True),
                    credential("b", name="B", is_default=True),
                ]
            )


class CredentialRemovalTestCase(unittest.TestCase):
    """CT-102 (RN-38): credencial ou modelo em uso nao pode sair."""

    def setUp(self) -> None:
        self.openai = credential("cred-openai", is_default=True)
        self.gemini = credential(
            "cred-gemini",
            name="Gemini",
            provider=LLMProvider.GEMINI,
            models=("gemini-3.8-flash", "gemini-3.8-pro"),
            default_model="gemini-3.8-flash",
        )
        self.assistants = [
            assistant("rh"),
            assistant("juridico", credential_id="cred-gemini", model="gemini-3.8-pro"),
            assistant("financeiro", credential_id="cred-gemini"),
        ]

    def test_assistants_using_lists_only_explicit_choices(self) -> None:
        self.assertEqual(
            [item.value for item in assistants_using(self.gemini.id, self.assistants)],
            ["juridico", "financeiro"],
        )
        self.assertEqual(assistants_using(self.openai.id, self.assistants), ())

    def test_followers_of_the_default(self) -> None:
        self.assertEqual(
            [item.value for item in assistants_following_default(self.assistants)],
            ["rh"],
        )

    def test_default_credential_cannot_be_removed(self) -> None:
        with self.assertRaises(LLMCredentialInUseError) as caught:
            ensure_removable(self.openai, iter(self.assistants))
        self.assertTrue(caught.exception.is_default)
        # Lista quem escolheu a padrao e quem a segue sem escolha.
        self.assertEqual(caught.exception.assistant_ids, ("rh",))

    def test_credential_in_use_lists_the_assistants(self) -> None:
        with self.assertRaises(LLMCredentialInUseError) as caught:
            ensure_removable(self.gemini, self.assistants)
        self.assertFalse(caught.exception.is_default)
        self.assertEqual(caught.exception.assistant_ids, ("juridico", "financeiro"))

    def test_unused_credential_can_be_removed(self) -> None:
        spare = credential("cred-spare", name="Reserva")
        ensure_removable(spare, self.assistants)

    def test_removing_a_model_in_use_fails(self) -> None:
        updated = credential(
            "cred-gemini",
            name="Gemini",
            provider=LLMProvider.GEMINI,
            models=("gemini-3.8-flash",),
            default_model="gemini-3.8-flash",
        )
        with self.assertRaises(LLMCredentialInUseError) as caught:
            ensure_models_removable(self.gemini, updated, self.assistants)
        self.assertEqual(caught.exception.models, ("gemini-3.8-pro",))
        self.assertEqual(caught.exception.assistant_ids, ("juridico",))

    def test_every_removed_model_in_use_is_reported_even_from_a_generator(self) -> None:
        current = credential(
            "cred-gemini",
            name="Gemini",
            provider=LLMProvider.GEMINI,
            models=("gemini-3.8-flash", "gemini-3.8-pro", "gemini-4-pro"),
            default_model="gemini-3.8-flash",
        )
        updated = credential(
            "cred-gemini",
            name="Gemini",
            provider=LLMProvider.GEMINI,
            models=("gemini-3.8-flash",),
            default_model="gemini-3.8-flash",
        )
        users = [
            assistant("juridico", credential_id="cred-gemini", model="gemini-3.8-pro"),
            assistant("compras", credential_id="cred-gemini", model="gemini-4-pro"),
        ]
        with self.assertRaises(LLMCredentialInUseError) as caught:
            ensure_models_removable(current, updated, (item for item in users))
        self.assertEqual(caught.exception.models, ("gemini-3.8-pro", "gemini-4-pro"))
        self.assertEqual(caught.exception.assistant_ids, ("juridico", "compras"))

    def test_assistant_on_the_default_model_follows_the_new_default(self) -> None:
        # O financeiro nao escolheu modelo: trocar o padrao da credencial nao o bloqueia.
        updated = credential(
            "cred-gemini",
            name="Gemini",
            provider=LLMProvider.GEMINI,
            models=("gemini-3.8-pro", "gemini-4-flash"),
            default_model="gemini-4-flash",
        )
        ensure_models_removable(self.gemini, updated, self.assistants)


class AssistantLLMFieldsTestCase(unittest.TestCase):
    """D11: quem segue a padrao pode guardar modelo; sem nada gravado, nada muda."""

    def test_assistant_defaults_keep_the_current_behaviour(self) -> None:
        plain = Assistant(id=AssistantId("rh"), name=AssistantName("RH"))
        self.assertIsNone(plain.llm_credential_id)
        self.assertIsNone(plain.llm_model)
        self.assertTrue(plain.retrieval_profile.is_empty)

    def test_follower_of_the_default_may_keep_a_model(self) -> None:
        follower = assistant("rh", model=" gpt-4o ")
        self.assertIsNone(follower.llm_credential_id)
        self.assertEqual(follower.llm_model, "gpt-4o")

    def test_model_name_follows_the_same_rules(self) -> None:
        with self.assertRaises(DomainValidationError):
            assistant("rh", credential_id="cred-openai", model="gpt 4o")

    def test_assistant_carries_its_retrieval_profile(self) -> None:
        profiled = Assistant(
            id=AssistantId("juridico"),
            name=AssistantName("Juridico"),
            retrieval_profile=RetrievalProfile(min_score=0.3),
        )
        self.assertEqual(profiled.retrieval_profile.min_score, 0.3)


class AuditActionsTestCase(unittest.TestCase):
    """RF-94: acoes novas; as antigas continuam para a trilha ja gravada (T5)."""

    def test_new_actions(self) -> None:
        expected = {
            "LLM_CREDENTIAL_CREATED": "llm_credential.created",
            "LLM_CREDENTIAL_UPDATED": "llm_credential.updated",
            "LLM_CREDENTIAL_DELETED": "llm_credential.deleted",
            "LLM_CREDENTIAL_DEFAULT_CHANGED": "llm_credential.default_changed",
            "LLM_CREDENTIAL_KEY_ROTATED": "llm_credential.key_rotated",
            "LLM_CREDENTIAL_TESTED": "llm_credential.tested",
            "ASSISTANT_LLM_CHANGED": "assistant.llm_changed",
            "ASSISTANT_RETRIEVAL_SETTINGS_CHANGED": "assistant.retrieval_settings_changed",
        }
        for member, value in expected.items():
            with self.subTest(member=member):
                self.assertEqual(AuditAction[member].value, value)

    def test_previous_actions_stay(self) -> None:
        self.assertEqual(AuditAction.LLM_API_KEY_CHANGED.value, "llm_api_key.changed")
        self.assertEqual(AuditAction.LLM_SETTINGS_CHANGED.value, "llm_settings.changed")


if __name__ == "__main__":
    unittest.main()
