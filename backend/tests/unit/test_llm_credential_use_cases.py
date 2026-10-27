"""SPEC-013 P3: credenciais, configuracao do assistente e resolucao (CT-101 a CT-105)."""

from __future__ import annotations

import unittest
from decimal import Decimal

from access_doubles import AccessFixture, admin, curator, make_user
from credential_doubles import (
    FAKE_KEY,
    InMemoryAssistants,
    InMemoryCredentials,
    PrefixCipher,
    RecordingGateway,
    assistant,
    credential,
    gemini,
)

from src.application.services import (
    LLMSource,
    resolve_llm_for_assistant,
    resolve_retrieval_settings,
)
from src.application.use_cases import (
    AssistantRefInput,
    CreateLLMCredentialInput,
    CreateLLMCredentialUseCase,
    DefaultChangeImpactInput,
    DeleteLLMCredentialUseCase,
    GetAssistantLLMUseCase,
    GetAssistantRetrievalUseCase,
    GetDefaultChangeImpactUseCase,
    LLMCredentialKeyMissingError,
    LLMCredentialKeyUnreadableError,
    LLMCredentialNotFoundError,
    LLMCredentialRefInput,
    ListLLMCredentialOptionsUseCase,
    ListLLMCredentialsUseCase,
    LLMModelInput,
    SetDefaultLLMCredentialUseCase,
    TestLLMCredentialInput,
    TestLLMCredentialUseCase,
    UpdateAssistantLLMInput,
    UpdateAssistantLLMUseCase,
    UpdateAssistantRetrievalInput,
    UpdateAssistantRetrievalUseCase,
    UpdateLLMCredentialInput,
    UpdateLLMCredentialUseCase,
)
from src.application.use_cases.manage_assistant_access import AssistantNotFoundError
from src.domain import (
    PROVIDER_ENDPOINTS,
    AccessDeniedError,
    AssistantId,
    AuditAction,
    DomainValidationError,
    LLMConnection,
    LLMCredentialId,
    LLMCredentialInUseError,
    LLMModelOption,
    LLMProvider,
    RetrievalDefaults,
    RetrievalProfile,
)

ENVIRONMENT = LLMConnection.from_environment(
    model="gpt-4o-mini", api_url=PROVIDER_ENDPOINTS[LLMProvider.OPENAI]
)
DEFAULTS = RetrievalDefaults(hybrid_enabled=True, candidates=30, top_k=5, min_score=0.10)


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.access = AccessFixture()
        self.credentials = InMemoryCredentials()
        self.assistants = InMemoryAssistants()
        self.cipher = PrefixCipher()
        self.ids = iter(f"cred-{n}" for n in range(1, 100))

    def common(self) -> dict[str, object]:
        return {
            "credentials": self.credentials,
            "assistants": self.assistants,
            "access_control": self.access.control,
        }

    def create(self, name: str = "OpenAI", **overrides: object):
        values: dict[str, object] = {
            "user": admin(),
            "name": name,
            "provider": "openai",
            "models": (LLMModelInput(name="gpt-4o-mini"), LLMModelInput(name="gpt-4o")),
            "default_model": "gpt-4o-mini",
            "api_key": FAKE_KEY,
        }
        values.update(overrides)
        use_case = CreateLLMCredentialUseCase(
            **self.common(), cipher=self.cipher, id_factory=lambda: next(self.ids)
        )
        return use_case.execute(CreateLLMCredentialInput(**values))  # type: ignore[arg-type]

    def update(self, credential_id: str, **overrides: object):
        current = self.credentials.get(LLMCredentialId(credential_id))
        values: dict[str, object] = {
            "user": admin(),
            "credential_id": credential_id,
            "name": current.name,
            "provider": current.provider.value,
            "models": tuple(LLMModelInput(name=name) for name in current.model_names),
            "default_model": current.default_model,
            "api_url": current.api_url,
        }
        values.update(overrides)
        return UpdateLLMCredentialUseCase(**self.common(), cipher=self.cipher).execute(
            UpdateLLMCredentialInput(**values)  # type: ignore[arg-type]
        )


class CreateCredentialTestCase(_Base):
    """RF-87, RN-37 (CT-101) e RN-39 (CT-104)."""

    def test_first_credential_becomes_default_and_key_is_stored_encrypted(self) -> None:
        created = self.create()
        self.assertTrue(created.is_default)
        self.assertTrue(created.key_configured)
        stored = self.credentials.get_encrypted_key(LLMCredentialId(created.id))
        self.assertNotEqual(stored, FAKE_KEY)
        self.assertEqual(self.cipher.decrypt(stored), FAKE_KEY)
        self.assertNotIn(FAKE_KEY, repr(created))
        event = self.access.audit.last(AuditAction.LLM_CREDENTIAL_CREATED)
        self.assertEqual(event.details["credential_id"], created.id)
        self.assertNotIn(FAKE_KEY, repr(event.details))
        self.assertNotIn(stored, repr(event.details))

    def test_second_credential_is_not_default_unless_requested(self) -> None:
        first = self.create()
        second = self.create(name="Gemini", provider="gemini",
                             models=(LLMModelInput(name="gemini-3.8-flash"),),
                             default_model="gemini-3.8-flash")
        self.assertFalse(second.is_default)
        third = self.create(name="Reserva", make_default=True)
        self.assertTrue(third.is_default)
        self.assertFalse(self.credentials.get(LLMCredentialId(first.id)).is_default)
        event = self.access.audit.last(AuditAction.LLM_CREDENTIAL_DEFAULT_CHANGED)
        self.assertEqual(event.details["previous_default_id"], first.id)

    def test_model_prices_are_kept(self) -> None:
        created = self.create(
            models=(
                LLMModelInput(name="gpt-4o-mini"),
                LLMModelInput(name="gpt-4o", input_per_1k=Decimal("0.0025"),
                              output_per_1k=Decimal("0.01")),
            )
        )
        priced = [model for model in created.models if model.name == "gpt-4o"][0]
        self.assertEqual(priced.input_per_1k, Decimal("0.0025"))
        event = self.access.audit.last(AuditAction.LLM_CREDENTIAL_CREATED)
        self.assertEqual(event.details["priced_models"], ["gpt-4o"])

    def test_key_is_required_and_name_is_unique_ignoring_case(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.create(api_key="   ")
        self.create(name="OpenAI")
        with self.assertRaises(DomainValidationError):
            self.create(name="  openai ")

    def test_invalid_input_saves_nothing(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.create(provider="custom", api_url="https://llm.exemplo.com/v1/chat?key=x")
        with self.assertRaises(DomainValidationError):
            self.create(default_model="gpt-5")
        self.assertEqual(self.credentials.items, {})

    def test_inputs_never_show_the_key_in_repr(self) -> None:
        # RN-39: tracebacks e logs de entrada nao podem carregar a chave.
        create = CreateLLMCredentialInput(
            user=admin(), name="x", provider="openai",
            models=(LLMModelInput(name="m"),), default_model="m", api_key=FAKE_KEY,
        )
        update = UpdateLLMCredentialInput(
            user=admin(), credential_id="c", name="x", provider="openai",
            models=(LLMModelInput(name="m"),), default_model="m", api_key=FAKE_KEY,
        )
        self.assertNotIn(FAKE_KEY, repr(create))
        self.assertNotIn(FAKE_KEY, repr(update))

    def test_created_default_lists_its_followers(self) -> None:
        self.assistants.save(assistant("rh"))
        self.assertEqual(self.create().following_assistant_ids, ("rh",))

    def test_only_admin(self) -> None:
        # CT-105: negativa auditada.
        with self.assertRaises(AccessDeniedError):
            self.create(user=curator("curadora", "rh"))
        self.assertEqual(self.access.audit.actions(), [AuditAction.ACCESS_DENIED])
        self.assertEqual(self.credentials.items, {})


class UpdateCredentialTestCase(_Base):
    """RF-87, RN-38 (CT-102) e rotacao da chave (CT-104)."""

    def setUp(self) -> None:
        super().setUp()
        self.openai_id = self.create().id
        self.gemini_id = self.create(
            name="Gemini", provider="gemini",
            models=(LLMModelInput(name="gemini-3.8-flash"), LLMModelInput(name="gemini-3.8-pro")),
            default_model="gemini-3.8-flash",
        ).id

    def test_update_without_key_keeps_the_stored_key(self) -> None:
        before = self.credentials.get_encrypted_key(LLMCredentialId(self.openai_id))
        updated = self.update(self.openai_id, name="OpenAI produção")
        self.assertEqual(updated.name, "OpenAI produção")
        self.assertTrue(updated.is_default)
        self.assertEqual(self.credentials.get_encrypted_key(LLMCredentialId(self.openai_id)), before)
        self.assertNotIn(AuditAction.LLM_CREDENTIAL_KEY_ROTATED, self.access.audit.actions())
        event = self.access.audit.last(AuditAction.LLM_CREDENTIAL_UPDATED)
        self.assertEqual(event.details["previous_name"], "OpenAI")

    def test_rotation_keeps_the_id_and_is_audited_without_the_key(self) -> None:
        self.update(self.openai_id, api_key="sk-nova-ficticia")
        stored = self.credentials.get_encrypted_key(LLMCredentialId(self.openai_id))
        self.assertEqual(self.cipher.decrypt(stored), "sk-nova-ficticia")
        event = self.access.audit.last(AuditAction.LLM_CREDENTIAL_KEY_ROTATED)
        self.assertEqual(event.resource_id, self.openai_id)
        self.assertNotIn("sk-nova-ficticia", repr(self.access.audit.events))

    def test_new_destination_requires_a_new_key(self) -> None:
        # D12: trocar provedor ou URL sem chave nova e recusado e nada muda.
        before = self.credentials.get(LLMCredentialId(self.openai_id))
        with self.assertRaises(DomainValidationError):
            self.update(self.openai_id, provider="custom",
                        api_url="https://llm.exemplo.com/v1/chat/completions")
        with self.assertRaises(DomainValidationError):
            self.update(self.openai_id, provider="gemini", api_url=None,
                        models=(LLMModelInput(name="gemini-3.8-flash"),),
                        default_model="gemini-3.8-flash", api_key="  ")
        self.assertEqual(self.credentials.get(LLMCredentialId(self.openai_id)), before)
        moved = self.update(self.openai_id, provider="custom",
                            api_url="https://llm.exemplo.com/v1/chat/completions",
                            api_key="sk-destino-novo-ficticia")
        self.assertEqual(moved.provider, "custom")
        self.assertIn(AuditAction.LLM_CREDENTIAL_KEY_ROTATED, self.access.audit.actions())

    def test_removing_a_model_in_use_is_refused(self) -> None:
        self.assistants.save(assistant("juridico", credential_id=self.gemini_id,
                                       model="gemini-3.8-pro"))
        with self.assertRaises(LLMCredentialInUseError) as caught:
            self.update(self.gemini_id, models=(LLMModelInput(name="gemini-3.8-flash"),))
        self.assertEqual(caught.exception.models, ("gemini-3.8-pro",))
        self.assertEqual(
            self.credentials.get(LLMCredentialId(self.gemini_id)).model_names,
            ("gemini-3.8-flash", "gemini-3.8-pro"),
        )

    def test_default_update_reports_followers_that_will_fall_back(self) -> None:
        self.assistants.save(assistant("rh", model="gpt-4o"))
        self.update(self.openai_id, models=(LLMModelInput(name="gpt-4o-mini"),))
        event = self.access.audit.last(AuditAction.LLM_CREDENTIAL_UPDATED)
        self.assertEqual(event.details["falling_back_assistant_ids"], ["rh"])

    def test_unknown_credential(self) -> None:
        with self.assertRaises(LLMCredentialNotFoundError):
            UpdateLLMCredentialUseCase(**self.common(), cipher=self.cipher).execute(
                UpdateLLMCredentialInput(
                    user=admin(), credential_id="nada", name="x", provider="openai",
                    models=(LLMModelInput(name="m"),), default_model="m",
                )
            )


class DeleteAndDefaultTestCase(_Base):
    """RN-37 e RN-38 nos casos de uso (CT-101, CT-102)."""

    def setUp(self) -> None:
        super().setUp()
        self.openai_id = self.create().id
        self.gemini_id = self.create(
            name="Gemini", provider="gemini",
            models=(LLMModelInput(name="gemini-3.8-flash"),),
            default_model="gemini-3.8-flash",
        ).id
        self.assistants.save(assistant("rh", model="gpt-4o"))
        self.assistants.save(assistant("financeiro"))

    def delete(self, credential_id: str) -> None:
        DeleteLLMCredentialUseCase(**self.common()).execute(
            LLMCredentialRefInput(user=admin(), credential_id=credential_id)
        )

    def test_default_cannot_be_deleted_and_lists_followers(self) -> None:
        with self.assertRaises(LLMCredentialInUseError) as caught:
            self.delete(self.openai_id)
        self.assertTrue(caught.exception.is_default)
        self.assertEqual(caught.exception.assistant_ids, ("rh", "financeiro"))

    def test_chosen_credential_cannot_be_deleted(self) -> None:
        self.assistants.save(assistant("juridico", credential_id=self.gemini_id))
        with self.assertRaises(LLMCredentialInUseError):
            self.delete(self.gemini_id)

    def test_unused_credential_is_deleted_and_audited(self) -> None:
        self.delete(self.gemini_id)
        self.assertIsNone(self.credentials.get(LLMCredentialId(self.gemini_id)))
        self.assertIsNone(self.credentials.get_encrypted_key(LLMCredentialId(self.gemini_id)))
        event = self.access.audit.last(AuditAction.LLM_CREDENTIAL_DELETED)
        self.assertEqual(event.details["name"], "Gemini")

    def test_impact_preview_before_switching_the_default(self) -> None:
        impact = GetDefaultChangeImpactUseCase(**self.common()).execute(
            DefaultChangeImpactInput(user=admin(), credential_id=self.gemini_id)
        )
        self.assertEqual(impact.following_assistant_ids, ("rh", "financeiro"))
        self.assertEqual(impact.falling_back_assistant_ids, ("rh",))
        simulated = GetDefaultChangeImpactUseCase(**self.common()).execute(
            DefaultChangeImpactInput(
                user=admin(), credential_id=self.openai_id, model_names=("gpt-4o-mini",)
            )
        )
        self.assertEqual(simulated.falling_back_assistant_ids, ("rh",))

    def test_set_default_switches_and_audits(self) -> None:
        result = SetDefaultLLMCredentialUseCase(**self.common()).execute(
            LLMCredentialRefInput(user=admin(), credential_id=self.gemini_id)
        )
        self.assertTrue(result.is_default)
        self.assertFalse(self.credentials.get(LLMCredentialId(self.openai_id)).is_default)
        event = self.access.audit.last(AuditAction.LLM_CREDENTIAL_DEFAULT_CHANGED)
        self.assertEqual(event.details["previous_default_id"], self.openai_id)
        self.assertEqual(event.details["falling_back_assistant_ids"], ["rh"])

    def test_set_default_on_the_current_default_changes_nothing(self) -> None:
        count = len(self.access.audit.events)
        SetDefaultLLMCredentialUseCase(**self.common()).execute(
            LLMCredentialRefInput(user=admin(), credential_id=self.openai_id)
        )
        self.assertEqual(len(self.access.audit.events), count)

    def test_list_shows_users_and_followers_without_the_key(self) -> None:
        self.assistants.save(assistant("juridico", credential_id=self.gemini_id))
        listed = {item.id: item for item in ListLLMCredentialsUseCase(**self.common()).execute(admin())}
        self.assertEqual(listed[self.openai_id].following_assistant_ids, ("rh", "financeiro"))
        self.assertEqual(listed[self.gemini_id].assistant_ids, ("juridico",))
        self.assertEqual(listed[self.gemini_id].following_assistant_ids, ())
        self.assertNotIn(FAKE_KEY, repr(listed))
        options = ListLLMCredentialOptionsUseCase(**self.common()).execute(admin())
        self.assertEqual([item.name for item in options], ["OpenAI", "Gemini"])
        self.assertFalse(hasattr(options[0], "api_url"))

    def test_curator_cannot_list_delete_or_switch(self) -> None:
        user = curator("curadora", "rh")
        for call in (
            lambda: ListLLMCredentialsUseCase(**self.common()).execute(user),
            lambda: ListLLMCredentialOptionsUseCase(**self.common()).execute(user),
            lambda: DeleteLLMCredentialUseCase(**self.common()).execute(
                LLMCredentialRefInput(user=user, credential_id=self.gemini_id)),
            lambda: SetDefaultLLMCredentialUseCase(**self.common()).execute(
                LLMCredentialRefInput(user=user, credential_id=self.gemini_id)),
        ):
            with self.subTest(call=call), self.assertRaises(AccessDeniedError):
                call()
        self.assertEqual(
            self.access.audit.actions().count(AuditAction.ACCESS_DENIED), 4
        )
        attempted = [
            event.details["attempted_action"]
            for event in self.access.audit.events
            if event.action == AuditAction.ACCESS_DENIED
        ]
        # Leituras negadas aparecem como leitura, nao como alteracao.
        self.assertEqual(attempted[:2], ["llm_credential.listed", "llm_credential.listed"])


class TestCredentialTestCase(_Base):
    """RF-89."""

    def setUp(self) -> None:
        super().setUp()
        self.openai_id = self.create().id
        self.gateway = RecordingGateway()
        self.calls: list[tuple[LLMConnection, str]] = []

    def factory(self, connection: LLMConnection, api_key: str) -> RecordingGateway:
        self.calls.append((connection, api_key))
        return self.gateway

    def run_test(self, **overrides: object):
        values: dict[str, object] = {"user": admin(), "credential_id": self.openai_id}
        values.update(overrides)
        return TestLLMCredentialUseCase(
            **self.common(), cipher=self.cipher, gateway_factory=self.factory
        ).execute(TestLLMCredentialInput(**values))  # type: ignore[arg-type]

    def test_calls_the_provider_with_the_chosen_model_and_decrypted_key(self) -> None:
        result = self.run_test(model="gpt-4o")
        self.assertTrue(result.ok)
        self.assertEqual(result.model, "gpt-4o")
        connection, api_key = self.calls[0]
        self.assertEqual(connection.model, "gpt-4o")
        self.assertEqual(connection.api_url, PROVIDER_ENDPOINTS[LLMProvider.OPENAI])
        self.assertEqual(api_key, FAKE_KEY)
        event = self.access.audit.last(AuditAction.LLM_CREDENTIAL_TESTED)
        self.assertEqual(event.details["llm_model"], "gpt-4o")
        self.assertNotIn(FAKE_KEY, repr(event.details))

    def test_default_model_when_none_and_refuses_unknown_models(self) -> None:
        self.assertEqual(self.run_test().model, "gpt-4o-mini")
        with self.assertRaises(DomainValidationError):
            self.run_test(model="gpt-5")

    def test_missing_key(self) -> None:
        self.credentials.keys.clear()
        with self.assertRaises(LLMCredentialKeyMissingError):
            self.run_test()

    def test_key_that_cannot_be_decrypted_is_not_a_provider_failure(self) -> None:
        # Chave mestra trocada: erro do servidor, sem chamar o provedor nem auditar o teste.
        class BrokenCipher(PrefixCipher):
            def decrypt(self, ciphertext: str) -> str:
                raise ValueError("Unable to decrypt stored secret.")

        self.cipher = BrokenCipher()
        with self.assertRaises(LLMCredentialKeyUnreadableError):
            self.run_test()
        self.assertEqual(self.calls, [])
        self.assertNotIn(AuditAction.LLM_CREDENTIAL_TESTED, self.access.audit.actions())

    def test_provider_failure_propagates(self) -> None:
        self.gateway.error = RuntimeError("401 do provedor")
        with self.assertRaises(RuntimeError):
            self.run_test()


class AssistantLLMTestCase(_Base):
    """RF-90 e D11."""

    def setUp(self) -> None:
        super().setUp()
        self.openai_id = self.create().id
        self.gemini_id = self.create(
            name="Gemini", provider="gemini",
            models=(LLMModelInput(name="gemini-3.8-flash"),),
            default_model="gemini-3.8-flash",
        ).id
        self.assistants.save(assistant("rh"))
        self.access.link_assistant("rh", "rh")

    def set_llm(self, user=None, **values: object):
        return UpdateAssistantLLMUseCase(
            assistants=self.assistants, access_control=self.access.control,
            credentials=self.credentials, environment=ENVIRONMENT,
        ).execute(UpdateAssistantLLMInput(user=user or admin(), assistant_id="rh", **values))  # type: ignore[arg-type]

    def get_llm(self, user=None):
        return GetAssistantLLMUseCase(
            assistants=self.assistants, access_control=self.access.control,
            credentials=self.credentials, environment=ENVIRONMENT,
        ).execute(AssistantRefInput(user=user or admin(), assistant_id="rh"))

    def test_nothing_stored_follows_the_default(self) -> None:
        described = self.get_llm()
        self.assertEqual((described.credential_id, described.model), (None, None))
        self.assertEqual(described.source, "default")
        self.assertEqual(described.effective_credential_id, self.openai_id)
        self.assertEqual(described.effective_model, "gpt-4o-mini")

    def test_choose_credential_and_model(self) -> None:
        described = self.set_llm(credential_id=self.gemini_id, model="gemini-3.8-flash")
        self.assertEqual(described.source, "assistant")
        self.assertEqual(described.effective_provider, "gemini")
        event = self.access.audit.last(AuditAction.ASSISTANT_LLM_CHANGED)
        self.assertEqual(event.details["credential_id"], self.gemini_id)
        self.assertIsNone(event.details["previous_credential_id"])

    def test_model_must_belong_to_the_chosen_credential(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.set_llm(credential_id=self.gemini_id, model="gpt-4o")

    def test_follower_model_must_exist_in_the_current_default_when_saving(self) -> None:
        described = self.set_llm(model="gpt-4o")
        self.assertEqual((described.credential_id, described.model), (None, "gpt-4o"))
        self.assertEqual(described.effective_model, "gpt-4o")
        with self.assertRaises(DomainValidationError):
            self.set_llm(model="gemini-3.8-flash")

    def test_follower_falls_back_when_the_default_changes(self) -> None:
        self.set_llm(model="gpt-4o")
        self.credentials.set_default(LLMCredentialId(self.gemini_id), updated_by="admin")
        described = self.get_llm()
        self.assertTrue(described.model_falls_back)
        self.assertEqual(described.effective_model, "gemini-3.8-flash")

    def test_without_credentials_a_model_cannot_be_stored(self) -> None:
        self.credentials.items.clear()
        with self.assertRaises(DomainValidationError):
            self.set_llm(model="gpt-4o")
        described = self.set_llm()
        self.assertEqual(described.source, "environment")
        self.assertEqual(described.effective_model, "gpt-4o-mini")

    def test_unknown_credential_or_assistant(self) -> None:
        with self.assertRaises(LLMCredentialNotFoundError):
            self.set_llm(credential_id="nada")
        with self.assertRaises(AssistantNotFoundError):
            UpdateAssistantLLMUseCase(
                assistants=self.assistants, access_control=self.access.control,
                credentials=self.credentials, environment=ENVIRONMENT,
            ).execute(UpdateAssistantLLMInput(user=admin(), assistant_id="nada"))

    def test_llm_change_keeps_the_retrieval_profile(self) -> None:
        # Sem atualizacao perdida: cada caso de uso grava so as proprias colunas.
        self.assistants.update_retrieval_profile(
            AssistantId("rh"), RetrievalProfile(min_score=0.3)
        )
        self.set_llm(credential_id=self.gemini_id)
        stored = self.assistants.get_by_id(AssistantId("rh"))
        self.assertEqual(stored.retrieval_profile, RetrievalProfile(min_score=0.3))
        self.assertEqual(stored.llm_credential_id, LLMCredentialId(self.gemini_id))

    def test_curator_reads_but_cannot_change_the_llm(self) -> None:
        # D7: a curadora do assistente ve o modelo, mas so o administrador escolhe.
        user = curator("curadora", "rh")
        self.assertEqual(self.get_llm(user).source, "default")
        with self.assertRaises(AccessDeniedError):
            self.set_llm(user, credential_id=self.gemini_id)
        with self.assertRaises(AccessDeniedError):
            self.get_llm(make_user("usuario", groups=("rh",)))


class AssistantRetrievalTestCase(_Base):
    """RF-91, D6, D7 e T3."""

    def setUp(self) -> None:
        super().setUp()
        self.assistants.save(assistant("rh"))
        self.assistants.save(assistant("financeiro"))
        self.access.link_assistant("rh", "rh")
        self.access.link_assistant("financeiro", "financeiro")

    def set_retrieval(self, user=None, assistant_id: str = "rh", **values: object):
        return UpdateAssistantRetrievalUseCase(
            assistants=self.assistants, access_control=self.access.control, defaults=DEFAULTS,
        ).execute(UpdateAssistantRetrievalInput(
            user=user or admin(), assistant_id=assistant_id, **values))  # type: ignore[arg-type]

    def test_nothing_stored_shows_the_defaults(self) -> None:
        described = GetAssistantRetrievalUseCase(
            assistants=self.assistants, access_control=self.access.control, defaults=DEFAULTS,
        ).execute(AssistantRefInput(user=admin(), assistant_id="rh"))
        self.assertEqual(described.min_score.effective, 0.10)
        self.assertIsNone(described.min_score.stored)
        self.assertEqual(described.min_score.origin, "default")

    def test_curator_of_the_assistant_sets_values_and_restores_defaults(self) -> None:
        user = curator("curadora", "rh")
        described = self.set_retrieval(user, min_score=0.3, hybrid_enabled=False)
        self.assertEqual(described.min_score.effective, 0.3)
        self.assertEqual(described.min_score.origin, "assistant")
        self.assertFalse(described.hybrid_enabled.effective)
        self.assertEqual(described.candidates.origin, "default")
        event = self.access.audit.last(AuditAction.ASSISTANT_RETRIEVAL_SETTINGS_CHANGED)
        self.assertEqual(event.details["settings"], {"hybrid_enabled": False, "min_score": 0.3})
        self.assertEqual(event.details["previous_settings"], {})
        restored = self.set_retrieval(user)
        self.assertEqual(restored.min_score.origin, "default")
        self.assertTrue(self.assistants.get_by_id(AssistantId("rh")).retrieval_profile.is_empty)

    def test_access_is_checked_before_existence(self) -> None:
        # Quem nao tem acesso recebe 403 tambem para assistente inexistente.
        with self.assertRaises(AccessDeniedError):
            self.set_retrieval(curator("curadora", "rh"), assistant_id="nao-existe", top_k=8)
        with self.assertRaises(AssistantNotFoundError):
            self.set_retrieval(admin(), assistant_id="nao-existe", top_k=8)

    def test_retrieval_change_keeps_the_llm_choice(self) -> None:
        self.assistants.update_llm_choice(
            AssistantId("rh"), credential_id=LLMCredentialId("cred-x"), model="m"
        )
        self.set_retrieval(min_score=0.3)
        stored = self.assistants.get_by_id(AssistantId("rh"))
        self.assertEqual((stored.llm_credential_id.value, stored.llm_model), ("cred-x", "m"))

    def test_curator_of_another_assistant_is_denied(self) -> None:
        with self.assertRaises(AccessDeniedError):
            self.set_retrieval(curator("curadora", "rh"), assistant_id="financeiro", top_k=8)
        self.assertTrue(
            self.assistants.get_by_id(AssistantId("financeiro")).retrieval_profile.is_empty
        )

    def test_ranges_and_effective_top_k(self) -> None:
        for values in ({"candidates": 101}, {"top_k": 0}, {"min_score": 1.5},
                       {"top_k": 20, "candidates": 10}):
            with self.subTest(values=values), self.assertRaises(DomainValidationError):
                self.set_retrieval(**values)
        narrow = RetrievalDefaults(hybrid_enabled=True, candidates=10, top_k=5, min_score=0.1)
        with self.assertRaises(DomainValidationError):
            UpdateAssistantRetrievalUseCase(
                assistants=self.assistants, access_control=self.access.control, defaults=narrow,
            ).execute(UpdateAssistantRetrievalInput(user=admin(), assistant_id="rh", top_k=15))


class ResolutionTestCase(_Base):
    """RN-40, RN-41, D8 e D11 na pergunta (CT-103)."""

    def setUp(self) -> None:
        super().setUp()
        priced = credential(
            "cred-openai", name="OpenAI", is_default=True,
        )
        priced = type(priced)(
            id=priced.id, name=priced.name, provider=priced.provider, api_url=priced.api_url,
            models=(
                LLMModelOption(name="gpt-4o-mini"),
                LLMModelOption(name="gpt-4o", input_per_1k=Decimal("0.0025"),
                               output_per_1k=Decimal("0.01")),
            ),
            default_model="gpt-4o-mini", is_default=True,
        )
        self.credentials.add(priced, encrypted_key=self.cipher.encrypt(FAKE_KEY))
        self.credentials.add(gemini(), encrypted_key=self.cipher.encrypt("sk-gemini-ficticia"))

    def resolve(self, item):
        return resolve_llm_for_assistant(
            item, credentials=self.credentials, cipher=self.cipher,
            environment=ENVIRONMENT, currency="USD",
        )

    def test_chosen_credential(self) -> None:
        resolved = self.resolve(assistant("juridico", credential_id="cred-gemini",
                                          model="gemini-3.8-pro"))
        self.assertEqual(resolved.source, LLMSource.ASSISTANT)
        self.assertEqual(resolved.connection.model, "gemini-3.8-pro")
        self.assertEqual(resolved.connection.provider, LLMProvider.GEMINI)
        self.assertEqual(resolved.api_key, "sk-gemini-ficticia")
        self.assertIsNone(resolved.pricing)
        self.assertNotIn("sk-gemini-ficticia", repr(resolved))

    def test_follower_uses_the_default_and_the_model_price(self) -> None:
        resolved = self.resolve(assistant("rh", model="gpt-4o"))
        self.assertEqual(resolved.source, LLMSource.DEFAULT)
        self.assertEqual(resolved.credential_name, "OpenAI")
        self.assertEqual(resolved.pricing.output_per_1k, Decimal("0.01"))
        self.assertEqual(resolved.api_key, FAKE_KEY)
        self.assertFalse(resolved.model_fell_back)

    def test_follower_falls_back_with_a_warning(self) -> None:
        self.credentials.set_default(LLMCredentialId("cred-gemini"), updated_by="admin")
        with self.assertLogs("src.application.services.llm_resolution", "WARNING") as logs:
            resolved = self.resolve(assistant("rh", model="gpt-4o"))
        self.assertTrue(resolved.model_fell_back)
        self.assertEqual(resolved.connection.model, "gemini-3.8-flash")
        self.assertNotIn("sk-gemini-ficticia", "".join(logs.output))

    def test_environment_when_there_is_no_credential(self) -> None:
        self.credentials.items.clear()
        self.credentials.keys.clear()
        resolved = self.resolve(assistant("rh"))
        self.assertEqual(resolved.source, LLMSource.ENVIRONMENT)
        self.assertEqual(resolved.connection, ENVIRONMENT)
        self.assertIsNone(resolved.api_key)

    def test_missing_chosen_credential_falls_to_the_default(self) -> None:
        with self.assertLogs("src.application.services.llm_resolution", "WARNING"):
            resolved = self.resolve(assistant("juridico", credential_id="apagada"))
        self.assertEqual(resolved.source, LLMSource.DEFAULT)

    def test_retrieval_settings_per_question(self) -> None:
        item = assistant("juridico")
        self.assertEqual(resolve_retrieval_settings(item, DEFAULTS).min_score, 0.10)
        from dataclasses import replace

        tuned = replace(item, retrieval_profile=RetrievalProfile(top_k=20))
        narrow = RetrievalDefaults(hybrid_enabled=True, candidates=10, top_k=5, min_score=0.1)
        with self.assertLogs("src.application.services.llm_resolution", "WARNING"):
            resolved = resolve_retrieval_settings(tuned, narrow)
        self.assertEqual(resolved.top_k, 10)


if __name__ == "__main__":
    unittest.main()
