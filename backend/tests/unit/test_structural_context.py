"""SPEC-20261026-012: contexto estrutural e regra de formato (CT-94, CT-95)."""

from __future__ import annotations

import unittest

from access_doubles import AccessFixture, make_user
from chat_doubles import (
    ScriptedLLM,
    ScriptedReranker,
    ScriptedVectorStore,
    WordTokenCounter,
    article_hit,
    build_retriever,
    hit,
)
from src.application.services import (
    CITATION_INSTRUCTION,
    FORMAT_INSTRUCTION,
    GroundedAnswerGenerator,
    RetrievalSettings,
    build_answer_instruction,
    fit_structural_context,
)
from src.application.use_cases import (
    ChatWithAssistantInput,
    ChatWithAssistantUseCase,
    EvaluateAssistantInput,
    EvaluateAssistantUseCase,
)
from src.domain import (
    AssistantId,
    CollectionName,
    Document,
    DocumentId,
    EvaluationItem,
    LegalReference,
)
from test_chat_flow import (
    ASSISTANT,
    CONVERSATION,
    GROUP,
    InMemoryAssistantRepository,
    InMemoryConversationRepository,
)

ASSISTANT_ID = AssistantId(ASSISTANT)
OWNER = make_user("user-1", groups=(GROUP,))

# Art. 5 de um regulamento ficticio, em quatro trechos.
ARTICLE_FIVE = [
    article_hit("lei", 10, "Art. 5º Compete ao conselho:"),
    article_hit("lei", 11, "I - aprovar o plano; II - fiscalizar as contas;"),
    article_hit("lei", 12, "X - ouvir os associados; XI - publicar o balanço;"),
    article_hit("lei", 13, "§ 1º O conselho se reúne mensalmente."),
]


def _retriever(vector_store, reranker=None, settings=None):
    return build_retriever(vector_store, reranker=reranker, settings=settings)


class StructuralRetrievalTestCase(unittest.TestCase):
    """D6 e D7: o artigo inteiro, em ordem, do documento certo."""

    def test_question_without_reference_does_not_read_articles(self) -> None:
        store = ScriptedVectorStore([], {"5": ARTICLE_FIVE})
        result = _retriever(store).structural_context(
            ASSISTANT_ID, "Quanto duram as ferias?", [], user_groups=frozenset()
        )
        self.assertIsNone(result)
        self.assertEqual(store.article_calls, [])

    def test_whole_article_in_order_with_the_user_groups(self) -> None:
        shuffled = [ARTICLE_FIVE[2], ARTICLE_FIVE[0], ARTICLE_FIVE[3], ARTICLE_FIVE[1]]
        store = ScriptedVectorStore([], {"5": shuffled})
        result = _retriever(store).structural_context(
            ASSISTANT_ID,
            "Explique o artigo 5",
            [],
            user_groups=frozenset({"juridico"}),
        )
        self.assertEqual(result.reference, LegalReference(article="5"))
        self.assertEqual(
            [item.chunk_id for item in result.results],
            ["lei:10", "lei:11", "lei:12", "lei:13"],
        )
        (call,) = store.article_calls
        self.assertEqual(call["article"], "5")
        self.assertEqual(call["collection"], CollectionName.from_assistant_id(ASSISTANT_ID).value)
        self.assertEqual(call["user_groups"], frozenset({"juridico"}))

    def test_article_not_found_returns_nothing(self) -> None:
        store = ScriptedVectorStore([], {})
        self.assertIsNone(
            _retriever(store).structural_context(
                ASSISTANT_ID, "artigo 99", [], user_groups=frozenset()
            )
        )

    def test_document_found_by_the_hybrid_search_wins(self) -> None:
        other = [article_hit("clt", 3, "Art. 5º Outro texto.", source_name="clt.txt")]
        store = ScriptedVectorStore([], {"5": other + ARTICLE_FIVE})
        candidates = [hit("x", "sem relacao"), ARTICLE_FIVE[1]]
        result = _retriever(store).structural_context(
            ASSISTANT_ID, "artigo 5", candidates, user_groups=frozenset()
        )
        self.assertEqual({item.document_id.value for item in result.results}, {"lei"})

    def test_document_name_decides_without_a_hybrid_hit(self) -> None:
        constitution = [
            article_hit("cf", 1, "Art. 5º Todos são iguais.", source_name="constituicao-ficticia.pdf")
        ]
        store = ScriptedVectorStore([], {"5": ARTICLE_FIVE + constitution})
        result = _retriever(store).structural_context(
            ASSISTANT_ID,
            "Explique o artigo 5 da constituição",
            [],
            user_groups=frozenset(),
        )
        self.assertEqual([item.chunk_id for item in result.results], ["cf:1"])

    def test_tie_keeps_every_document_ordered_by_name(self) -> None:
        other = [article_hit("abc", 2, "Art. 5º Texto.", source_name="abc.txt")]
        store = ScriptedVectorStore([], {"5": ARTICLE_FIVE + other})
        result = _retriever(store).structural_context(
            ASSISTANT_ID, "artigo 5", [], user_groups=frozenset()
        )
        self.assertEqual(
            [item.chunk_id for item in result.results],
            ["abc:2", "lei:10", "lei:11", "lei:12", "lei:13"],
        )

    def test_two_articles_with_the_same_number_in_one_document(self) -> None:
        transitory = [
            article_hit("lei", 90, "Art. 5º Disposicao transitoria."),
            article_hit("lei", 91, "continua a disposicao."),
        ]
        store = ScriptedVectorStore([], {"5": ARTICLE_FIVE + transitory})
        retriever = _retriever(store)
        first = retriever.structural_context(
            ASSISTANT_ID, "artigo 5", [], user_groups=frozenset()
        )
        self.assertEqual([item.chunk_index for item in first.results], [10, 11, 12, 13])
        hinted = retriever.structural_context(
            ASSISTANT_ID, "artigo 5", [transitory[1]], user_groups=frozenset()
        )
        self.assertEqual([item.chunk_index for item in hinted.results], [90, 91])

    def test_item_brings_the_caput_and_the_item(self) -> None:
        reranker = ScriptedReranker()
        store = ScriptedVectorStore([], {"5": ARTICLE_FIVE})
        result = _retriever(store, reranker).structural_context(
            ASSISTANT_ID, "o que diz o inciso XI do art. 5º?", [], user_groups=frozenset()
        )
        self.assertEqual([item.chunk_id for item in result.results], ["lei:10", "lei:12"])
        self.assertEqual(reranker.calls, [])

    def test_part_not_found_by_marker_falls_back_to_the_reranker(self) -> None:
        reranker = ScriptedReranker(
            {
                ARTICLE_FIVE[1].text: 0.8,
                ARTICLE_FIVE[2].text: 0.1,
                ARTICLE_FIVE[3].text: 0.9,
            }
        )
        store = ScriptedVectorStore([], {"5": ARTICLE_FIVE})
        settings = RetrievalSettings(top_n=1)
        result = _retriever(store, reranker, settings).structural_context(
            ASSISTANT_ID, "inciso XL do art. 5", [], user_groups=frozenset()
        )
        self.assertEqual([item.chunk_id for item in result.results], ["lei:10", "lei:13"])


class StructuralBudgetTestCase(unittest.TestCase):
    """D8 e RN-36: o que nao cabe e avisado, nunca cortado em silencio."""

    def test_everything_fits_without_notice(self) -> None:
        chunks, notice = fit_structural_context(
            ARTICLE_FIVE, LegalReference("5"), WordTokenCounter(), 1000
        )
        self.assertEqual([chunk.number for chunk in chunks], [1, 2, 3, 4])
        self.assertIsNone(notice)

    def test_omitted_items_are_named(self) -> None:
        chunks, notice = fit_structural_context(
            ARTICLE_FIVE, LegalReference("5"), WordTokenCounter(), 15
        )
        self.assertEqual(len(chunks), 2)
        self.assertIn("Art. 5", notice)
        self.assertIn("X a § 1º", notice)

    def test_settings_default_and_validation(self) -> None:
        self.assertEqual(RetrievalSettings().structural_context_token_budget, 16000)
        with self.assertRaises(ValueError):
            RetrievalSettings(structural_context_token_budget=0)


class FormatInstructionTestCase(unittest.TestCase):
    """CT-95: regra de formato global, depois do prompt do assistente (D2)."""

    def test_order_of_the_system_instruction(self) -> None:
        instruction = build_answer_instruction("Aja como advogado.")
        self.assertLess(instruction.index("Aja como advogado."), instruction.index(FORMAT_INSTRUCTION))
        self.assertIn(CITATION_INSTRUCTION, instruction)

    def test_format_rule_content(self) -> None:
        for expected in (
            "sucint",
            "todos os itens",
            "resumo explicativo",
            "apenas agrupe e sintetize",
            "Nunca acrescente",
            "use os termos do proprio texto",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, FORMAT_INSTRUCTION)

    def test_notice_goes_last(self) -> None:
        instruction = build_answer_instruction(None, notice="Aviso de teste.")
        self.assertTrue(instruction.endswith("Aviso de teste."))


class StructuralChatScenario:
    def __init__(
        self,
        *,
        results,
        articles,
        settings: RetrievalSettings | None = None,
        answer: str = "I - aprovar [2]. Resumo [1].",
        low_scores: bool = True,
    ) -> None:
        self.conversations = InMemoryConversationRepository()
        self.vector_store = ScriptedVectorStore(results, articles)
        scores = {item.text: 0.05 for batch in results for item in batch}
        self.reranker = ScriptedReranker(scores if low_scores else None)
        self.llm = ScriptedLLM(answer)
        access = AccessFixture()
        access.link_assistant(ASSISTANT, GROUP)
        self.access = access
        self.use_case = ChatWithAssistantUseCase(
            assistant_repository=InMemoryAssistantRepository("Aja como advogado."),
            conversation_repository=self.conversations,
            context_retriever=build_retriever(
                self.vector_store, reranker=self.reranker, settings=settings
            ),
            answer_generator=GroundedAnswerGenerator(llm_gateway=self.llm),
            token_counter=WordTokenCounter(),
            access_control=access.control,
        )

    def audit_events(self):
        return self.access.audit.events

    def _input(self, question: str) -> ChatWithAssistantInput:
        return ChatWithAssistantInput(
            user=OWNER, conversation_id=CONVERSATION, question=question
        )

    def ask(self, question: str):
        return self.use_case.execute(self._input(question))

    def ask_stream(self, question: str):
        events = list(self.use_case.start_stream(self._input(question)))
        return events[-1].result


class StructuralChatTestCase(unittest.TestCase):
    """RF-85: a pergunta pelo artigo responde mesmo com nota baixa no reranking."""

    def _scenario(self, **kwargs) -> StructuralChatScenario:
        kwargs.setdefault("results", [[hit("x", "trecho sem relacao", score=0.05)]])
        kwargs.setdefault("articles", {"5": ARTICLE_FIVE})
        return StructuralChatScenario(**kwargs)

    def test_whole_article_reaches_the_llm_in_order(self) -> None:
        scenario = self._scenario()
        with self.assertLogs(
            "src.application.use_cases.chat_with_assistant", level="INFO"
        ) as logs:
            result = scenario.ask("Explique o artigo 5")
        self.assertFalse(result.fallback_used)
        self.assertEqual(result.used_context_chunks, 4)
        (call,) = scenario.llm.calls
        self.assertEqual(
            [chunk.chunk_id for chunk in call["context_chunks"]],
            ["lei:10", "lei:11", "lei:12", "lei:13"],
        )
        self.assertIn(FORMAT_INSTRUCTION, call["system_instruction"])
        self.assertEqual(scenario.reranker.calls, [])
        structural = [
            record for record in logs.records if record.getMessage() == "chat.context.structural"
        ]
        self.assertEqual(len(structural), 1)
        self.assertEqual(structural[0].article, "5")
        self.assertEqual(structural[0].context_chunks, 4)

    def test_audit_lists_only_the_chunks_sent_to_the_llm(self) -> None:
        """Revisao B2: o artigo lido inteiro nao infla a trilha de auditoria."""
        scenario = self._scenario(
            settings=RetrievalSettings(structural_context_token_budget=15)
        )
        scenario.ask("Explique o artigo 5")
        retrieved = [
            event.details["retrieved_documents"]
            for event in scenario.audit_events()
            if "retrieved_documents" in event.details
        ][-1]
        self.assertEqual([item["chunk_id"] for item in retrieved], ["lei:10", "lei:11"])

    def test_streaming_uses_the_same_context(self) -> None:
        scenario = self._scenario()
        result = scenario.ask_stream("Explique o artigo 5")
        self.assertFalse(result.fallback_used)
        (call,) = scenario.llm.calls
        self.assertEqual(len(call["context_chunks"]), 4)

    def test_user_groups_reach_the_article_read(self) -> None:
        scenario = self._scenario()
        scenario.ask("Explique o artigo 5")
        (call,) = scenario.vector_store.article_calls
        self.assertEqual(call["user_groups"], OWNER.groups)

    def test_article_out_of_reach_keeps_the_fallback(self) -> None:
        """RN-34: sem trecho legivel do artigo, vale a nota minima de sempre."""
        scenario = self._scenario(articles={})
        result = scenario.ask("Explique o artigo 5")
        self.assertTrue(result.fallback_used)
        self.assertEqual(scenario.llm.calls, [])

    def test_answer_without_citation_still_falls_back(self) -> None:
        """RN-35."""
        scenario = self._scenario(answer="Resposta sem citacao.")
        self.assertTrue(scenario.ask("Explique o artigo 5").fallback_used)

    def test_budget_notice_reaches_the_system_instruction(self) -> None:
        scenario = self._scenario(
            settings=RetrievalSettings(structural_context_token_budget=15)
        )
        scenario.ask("Explique o artigo 5")
        (call,) = scenario.llm.calls
        self.assertEqual(len(call["context_chunks"]), 2)
        self.assertIn("X a § 1º", call["system_instruction"])

    def test_questions_without_reference_follow_the_hybrid_search(self) -> None:
        scenario = self._scenario(
            results=[[hit("d1", "Ferias de trinta dias.", score=0.9)]],
            low_scores=False,
        )
        result = scenario.ask("Quanto duram as ferias?")
        self.assertFalse(result.fallback_used)
        self.assertEqual(scenario.vector_store.article_calls, [])
        self.assertEqual(len(scenario.reranker.calls), 1)


class StructuralEvaluationTestCase(unittest.TestCase):
    """A avaliacao usa o mesmo caminho estrutural do chat."""

    def test_retrieved_sources_come_from_the_article(self) -> None:
        store = ScriptedVectorStore([[hit("x", "sem relacao", score=0.9)]], {"5": ARTICLE_FIVE})

        class Documents:
            def list_by_assistant(self, assistant_id):
                return [
                    Document(
                        id=DocumentId("lei"),
                        assistant_id=assistant_id,
                        source_name="regulamento.txt",
                        content_hash="h",
                    )
                ]

        use_case = EvaluateAssistantUseCase(
            document_repository=Documents(),
            context_retriever=build_retriever(store),
            token_counter=WordTokenCounter(),
        )
        report = use_case.execute(
            EvaluateAssistantInput(
                assistant_id=ASSISTANT,
                items=(
                    EvaluationItem(
                        id="q1",
                        question="Explique o artigo 5",
                        expected_answer="Compete ao conselho aprovar e fiscalizar.",
                        source_documents=("regulamento.txt",),
                    ),
                ),
            )
        )
        self.assertEqual(report.metrics["recall_at_k"], 1.0)


if __name__ == "__main__":
    unittest.main()
