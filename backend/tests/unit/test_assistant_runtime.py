"""SPEC-013 P4: o chat usa a configuracao do assistente a cada pergunta (CT-106)."""

from __future__ import annotations

import unittest
from dataclasses import replace
from decimal import Decimal

from access_doubles import AccessFixture
from chat_doubles import (
    ScriptedLLM,
    ScriptedVectorStore,
    WordTokenCounter,
    build_retriever,
    hit,
)
from credential_doubles import FAKE_KEY, InMemoryCredentials, PrefixCipher, gemini
from operations_doubles import InMemoryUsageRecords, InMemoryUsageSettings
from test_chat_flow import (
    ASSISTANT,
    FALLBACK,
    GROUP,
    OWNER,
    InMemoryConversationRepository,
)

from src.application.services import (
    GroundedAnswerGenerator,
    LLMSource,
    ResolvedLLM,
    RetrievalSettings,
    UsageGovernance,
    UsageSettings,
    assistant_retrieval_settings,
    build_assistant_runtime,
)
from src.application.use_cases import ChatWithAssistantInput, ChatWithAssistantUseCase
from src.domain import (
    PROVIDER_ENDPOINTS,
    Assistant,
    AssistantId,
    AssistantName,
    AuthenticatedUser,
    LLMConnection,
    LLMCredential,
    LLMCredentialId,
    LLMModelOption,
    LLMPricing,
    LLMProvider,
    RetrievalProfile,
    TokenUsage,
)

ENVIRONMENT = LLMConnection.from_environment(
    model="gpt-4o-mini", api_url=PROVIDER_ENDPOINTS[LLMProvider.OPENAI]
)
BASE = RetrievalSettings(candidates=30, top_n=5, min_score=0.10, context_token_budget=1234)
PRICED = LLMCredential(
    id=LLMCredentialId("cred-openai"),
    name="OpenAI",
    provider=LLMProvider.OPENAI,
    api_url=PROVIDER_ENDPOINTS[LLMProvider.OPENAI],
    models=(
        LLMModelOption(name="gpt-4o-mini"),
        LLMModelOption(name="gpt-4o", input_per_1k=Decimal("1"), output_per_1k=Decimal("2")),
    ),
    default_model="gpt-4o-mini",
    is_default=True,
)


def assistant(**changes: object) -> Assistant:
    return replace(Assistant(id=AssistantId(ASSISTANT), name=AssistantName("RH")), **changes)


def credentials() -> tuple[InMemoryCredentials, PrefixCipher]:
    cipher = PrefixCipher()
    repository = InMemoryCredentials()
    repository.add(PRICED, encrypted_key=cipher.encrypt(FAKE_KEY))
    repository.add(gemini(), encrypted_key=cipher.encrypt("sk-gemini-ficticia"))
    return repository, cipher


class HybridToggleTestCase(unittest.TestCase):
    """D3 e RN-42: desligada, so a parte densa; os filtros continuam."""

    def search(self, hybrid: bool) -> dict[str, object]:
        store = ScriptedVectorStore([[hit("doc-1", "Ferias de trinta dias.")]])
        retriever = build_retriever(store).with_settings(
            RetrievalSettings(hybrid_enabled=hybrid)
        )
        retriever.search(
            AssistantId(ASSISTANT), "ferias de trinta dias", user_groups=frozenset({GROUP})
        )
        return store.calls[0]

    def test_hybrid_on_sends_the_sparse_vector(self) -> None:
        self.assertFalse(self.search(True)["sparse_vector"].is_empty)

    def test_hybrid_off_sends_only_the_dense_vector_with_the_same_filters(self) -> None:
        call = self.search(False)
        self.assertTrue(call["sparse_vector"].is_empty)
        self.assertEqual(call["user_groups"], frozenset({GROUP}))
        self.assertTrue(call["dense_vector"])

    def test_with_settings_keeps_the_gateways(self) -> None:
        store = ScriptedVectorStore([[], []])
        base = build_retriever(store)
        tuned = base.for_profile(candidates=12, top_n=3, min_score=0.4, hybrid_enabled=False)
        tuned.search(AssistantId(ASSISTANT), "pergunta", user_groups=frozenset())
        self.assertEqual(store.calls[0]["limit"], 12)
        self.assertEqual(base.settings.candidates, RetrievalSettings().candidates)


class BuildRuntimeTestCase(unittest.TestCase):
    """RN-40, RN-41 e D8 reunidos para uma pergunta."""

    def setUp(self) -> None:
        self.credentials, self.cipher = credentials()
        self.built: list[ResolvedLLM] = []

    def build(self, item: Assistant):
        def builder(resolved: ResolvedLLM) -> ScriptedLLM:
            self.built.append(resolved)
            return ScriptedLLM("ok")

        return build_assistant_runtime(
            item,
            base_settings=BASE,
            credentials=self.credentials,
            cipher=self.cipher,
            environment=ENVIRONMENT,
            currency="USD",
            gateway_builder=builder,
        )

    def test_profile_over_the_environment_keeping_the_budgets(self) -> None:
        runtime = self.build(
            assistant(retrieval_profile=RetrievalProfile(min_score=0.3, hybrid_enabled=False))
        )
        self.assertEqual(runtime.retrieval.min_score, 0.3)
        self.assertFalse(runtime.retrieval.hybrid_enabled)
        self.assertEqual(runtime.retrieval.candidates, 30)
        self.assertEqual(runtime.retrieval.context_token_budget, 1234)

    def test_llm_model_price_and_key_reach_the_builder(self) -> None:
        runtime = self.build(assistant(llm_model="gpt-4o"))
        (resolved,) = self.built
        self.assertEqual(resolved.api_key, FAKE_KEY)
        self.assertEqual(runtime.usage_model, "gpt-4o")
        self.assertEqual(runtime.usage_pricing.output_per_1k, Decimal("2"))
        self.assertEqual(runtime.llm.source, LLMSource.DEFAULT)

    def test_log_fields_never_carry_the_key(self) -> None:
        runtime = self.build(
            assistant(llm_credential_id=LLMCredentialId("cred-gemini"))
        )
        fields = runtime.log_fields()
        self.assertEqual(fields["llm_provider"], "gemini")
        self.assertTrue(fields["has_llm_credential"])
        self.assertNotIn("sk-gemini-ficticia", repr(fields))
        self.assertNotIn("sk-gemini-ficticia", repr(runtime))

    def test_retrieval_settings_alone_for_calibration(self) -> None:
        tuned = assistant_retrieval_settings(
            assistant(retrieval_profile=RetrievalProfile(candidates=50, top_k=8)), BASE
        )
        self.assertEqual((tuned.candidates, tuned.top_n, tuned.min_score), (50, 8, 0.10))


class ChatUsesTheAssistantRuntimeTestCase(unittest.TestCase):
    """CT-106: chat com e sem streaming segue o assistente; consumo com o preco dele."""

    def setUp(self) -> None:
        self.credentials, self.cipher = credentials()
        self.access = AccessFixture()
        self.access.link_assistant(ASSISTANT, GROUP)
        self.records = InMemoryUsageRecords()
        self.base_llm = ScriptedLLM("nunca usado [1].")
        self.assistant_llms: list[ScriptedLLM] = []
        self.resolved: list[ResolvedLLM] = []

    def chat(self, item: Assistant, *, score: float = 0.9, stream: bool = False):
        store = ScriptedVectorStore([[hit("doc-1", "Ferias de trinta dias.", score=score)]])
        self.store = store

        class Assistants:
            def get_by_id(self, assistant_id: AssistantId) -> Assistant | None:
                return item

        def builder(resolved: ResolvedLLM) -> ScriptedLLM:
            self.resolved.append(resolved)
            llm = ScriptedLLM(
                "As ferias duram trinta dias [1].",
                usage=TokenUsage(input_tokens=1000, output_tokens=1000),
            )
            self.assistant_llms.append(llm)
            return llm

        def resolver(current: Assistant):
            return build_assistant_runtime(
                current,
                base_settings=BASE,
                credentials=self.credentials,
                cipher=self.cipher,
                environment=ENVIRONMENT,
                currency="USD",
                gateway_builder=builder,
            )

        use_case = ChatWithAssistantUseCase(
            assistant_repository=Assistants(),
            conversation_repository=InMemoryConversationRepository(),
            context_retriever=build_retriever(store, settings=RetrievalSettings(min_score=0.99)),
            answer_generator=GroundedAnswerGenerator(llm_gateway=self.base_llm),
            token_counter=WordTokenCounter(),
            access_control=self.access.control,
            usage_governance=UsageGovernance(
                limiter=self.records,
                record_repository=self.records,
                settings_repository=InMemoryUsageSettings(),
                settings=UsageSettings(
                    pricing=LLMPricing(input_per_1k=Decimal("9"), output_per_1k=Decimal("9")),
                    model="modelo-do-ambiente",
                ),
            ),
            runtime_resolver=resolver,
        )
        data = ChatWithAssistantInput(
            user=OWNER, conversation_id="conv-1", question="Quanto duram as ferias?"
        )
        if stream:
            events = list(use_case.start_stream(data))
            return events
        return use_case.execute(data)

    def test_answer_comes_from_the_assistant_llm_with_its_settings(self) -> None:
        result = self.chat(assistant(llm_model="gpt-4o"))
        self.assertFalse(result.fallback_used)
        self.assertEqual(self.base_llm.calls, [])
        self.assertEqual(len(self.assistant_llms[0].calls), 1)
        self.assertEqual(self.resolved[0].connection.model, "gpt-4o")
        # Os parametros do injetado (min_score 0,99) nao valem: vale o ambiente (0,10).
        self.assertEqual(self.store.calls[0]["limit"], 30)
        (record,) = self.records.records
        self.assertEqual(record.model, "gpt-4o")

    def test_usage_uses_the_model_price_or_the_environment(self) -> None:
        self.chat(assistant(llm_model="gpt-4o"))
        self.chat(assistant())
        priced, unpriced = self.records.records
        # 1.000 tokens de entrada e 1.000 de saida: 1 + 2 com o preco do modelo.
        self.assertEqual(priced.estimated_cost, Decimal("3"))
        self.assertEqual(unpriced.model, "gpt-4o-mini")
        self.assertEqual(
            unpriced.estimated_cost,
            LLMPricing(input_per_1k=Decimal("9"), output_per_1k=Decimal("9")).estimate(
                unpriced.usage
            ),
        )

    def test_assistant_threshold_decides_the_fallback(self) -> None:
        result = self.chat(
            assistant(retrieval_profile=RetrievalProfile(min_score=0.95)), score=0.9
        )
        self.assertTrue(result.fallback_used)
        self.assertIn(FALLBACK, result.assistant_message.content)

    def test_hybrid_off_reaches_the_vector_store(self) -> None:
        self.chat(assistant(retrieval_profile=RetrievalProfile(hybrid_enabled=False)))
        self.assertTrue(self.store.calls[0]["sparse_vector"].is_empty)
        self.assertEqual(self.store.calls[0]["user_groups"], frozenset({GROUP}))

    def test_streaming_follows_the_same_runtime(self) -> None:
        events = self.chat(assistant(llm_credential_id=LLMCredentialId("cred-gemini")), stream=True)
        self.assertEqual(events[-1].kind, "done")
        self.assertEqual(self.resolved[0].connection.provider, LLMProvider.GEMINI)
        self.assertEqual(self.records.records[0].model, "gemini-3.8-flash")


class UsageOverrideTestCase(unittest.TestCase):
    def test_record_without_override_keeps_the_environment(self) -> None:
        records = InMemoryUsageRecords()
        governance = UsageGovernance(
            limiter=records,
            record_repository=records,
            settings_repository=InMemoryUsageSettings(),
            settings=UsageSettings(model="ambiente"),
        )
        user = AuthenticatedUser(id="u", name="u", roles=frozenset(), groups=frozenset())
        governance.record(user, conversation_id=None, assistant_id=None, usage=TokenUsage())
        governance.record(
            user, conversation_id=None, assistant_id=None, usage=TokenUsage(),
            model="gpt-4o", pricing=LLMPricing(currency="BRL"),
        )
        self.assertEqual([item.model for item in records.records], ["ambiente", "gpt-4o"])


if __name__ == "__main__":
    unittest.main()
