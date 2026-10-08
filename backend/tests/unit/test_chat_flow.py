"""SPEC-20261007-003: grafo conversacional (CT-14, CT-15, CT-16, CT-17)."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from access_doubles import AccessFixture, make_user
from chat_doubles import (
    ScriptedLLM,
    ScriptedReranker,
    ScriptedVectorStore,
    WordTokenCounter,
    build_retriever,
    hit,
)
from src.application.services import (
    CITATION_INSTRUCTION,
    REWRITE_INSTRUCTION,
    GroundedAnswerGenerator,
    RetrievalSettings,
)
from src.application.use_cases import (
    ChatWithAssistantInput,
    ChatWithAssistantUseCase,
    ConversationNotFoundError,
)
from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    ChatMessage,
    Conversation,
    ConversationId,
    MessageId,
    MessageRole,
    SearchResult,
)

CONVERSATION = "conv-1"
ASSISTANT = "assistant-1"
FALLBACK = "Nao encontrei contexto suficiente"
BASE_TIME = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
GROUP = "rh"
OWNER = make_user("user-1", groups=(GROUP,))


class InMemoryAssistantRepository:
    def __init__(self, initial_prompt: str | None = None) -> None:
        self._assistant = Assistant(
            id=AssistantId(ASSISTANT),
            name=AssistantName("RH"),
            initial_prompt=initial_prompt,
        )

    def get_by_id(self, assistant_id: AssistantId) -> Assistant | None:
        return self._assistant if assistant_id == self._assistant.id else None


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self.conversation = Conversation(
            id=ConversationId(CONVERSATION),
            assistant_id=AssistantId(ASSISTANT),
            owner_user_id=OWNER.id,
        )
        self.messages: list[ChatMessage] = []

    def get_by_id(self, conversation_id: ConversationId) -> Conversation | None:
        if conversation_id != self.conversation.id:
            return None
        return self.conversation

    def save_message(self, message: ChatMessage) -> ChatMessage:
        self.messages.append(message)
        return message

    def list_messages(self, conversation_id: ConversationId) -> list[ChatMessage]:
        return list(self.messages)

    def add_turn(self, question: str, answer: str) -> None:
        for role, content in (
            (MessageRole.USER, question),
            (MessageRole.ASSISTANT, answer),
        ):
            index = len(self.messages)
            self.messages.append(
                ChatMessage(
                    id=MessageId(f"msg-{index}"),
                    conversation_id=ConversationId(CONVERSATION),
                    role=role,
                    content=content,
                    created_at=BASE_TIME + timedelta(seconds=index),
                )
            )


class Scenario:
    def __init__(
        self,
        *,
        results: list[list[SearchResult]],
        answers: tuple[str, ...] = ("Resposta [1].",),
        scores: dict[str, float] | None = None,
        settings: RetrievalSettings | None = None,
        initial_prompt: str | None = None,
    ) -> None:
        self.conversations = InMemoryConversationRepository()
        self.vector_store = ScriptedVectorStore(results)
        self.reranker = ScriptedReranker(scores)
        self.llm = ScriptedLLM(*answers)
        self.access = AccessFixture()
        self.access.link_assistant(ASSISTANT, GROUP)
        self.use_case = ChatWithAssistantUseCase(
            assistant_repository=InMemoryAssistantRepository(initial_prompt),
            conversation_repository=self.conversations,
            context_retriever=build_retriever(
                self.vector_store,
                reranker=self.reranker,
                settings=settings,
            ),
            answer_generator=GroundedAnswerGenerator(llm_gateway=self.llm),
            token_counter=WordTokenCounter(),
            access_control=self.access.control,
        )

    def ask(
        self,
        question: str,
        conversation_id: str = CONVERSATION,
        top_k: int | None = None,
        user=OWNER,
    ):
        return self.use_case.execute(
            ChatWithAssistantInput(
                user=user,
                conversation_id=conversation_id,
                question=question,
                top_k=top_k,
            )
        )


class AnswerWithSourcesTestCase(unittest.TestCase):
    """Cenario "Resposta com fontes" (RF-37)."""

    def setUp(self) -> None:
        self.scenario = Scenario(
            results=[
                [
                    hit(
                        "doc-1",
                        "Ferias sao de trinta dias.",
                        source_name="politica.pdf",
                        section_path="Ferias > Duracao",
                        page=3,
                    ),
                    hit("doc-2", "Recesso de estagio.", score=0.7, index=4),
                ]
            ],
            answers=("As ferias duram trinta dias [1].",),
            initial_prompt="Aja como especialista em RH.",
        )
        self.result = self.scenario.ask("Quanto duram as ferias?")

    def test_answer_carries_the_cited_source(self) -> None:
        self.assertFalse(self.result.fallback_used)
        self.assertEqual(self.result.used_context_chunks, 2)
        (citation,) = self.result.citations
        self.assertEqual(citation.number, 1)
        self.assertEqual(citation.document_id, "doc-1")
        self.assertEqual(citation.chunk_id, "doc-1:0")
        self.assertEqual(citation.source_name, "politica.pdf")
        self.assertEqual(citation.section_path, "Ferias > Duracao")
        self.assertEqual(citation.page, 3)
        self.assertEqual(citation.excerpt, "Ferias sao de trinta dias.")
        self.assertAlmostEqual(citation.score, 0.9)

    def test_citations_are_persisted_with_the_assistant_message(self) -> None:
        user_message, assistant_message = self.scenario.conversations.messages
        self.assertEqual(user_message.citations, ())
        self.assertEqual(assistant_message.role, MessageRole.ASSISTANT)
        self.assertEqual(len(assistant_message.citations), 1)
        self.assertEqual(assistant_message.citations[0].source_name, "politica.pdf")

    def test_llm_receives_numbered_chunks_and_the_citation_instruction(
        self,
    ) -> None:
        (call,) = self.scenario.llm.calls
        self.assertIn("Aja como especialista em RH.", call["prompt"])
        self.assertIn(CITATION_INSTRUCTION, call["prompt"])
        self.assertIn("Quanto duram as ferias?", call["prompt"])
        self.assertEqual(
            [chunk.number for chunk in call["context_chunks"]], [1, 2]
        )
        self.assertEqual(call["context_chunks"][0].source_name, "politica.pdf")

    def test_search_is_restricted_to_the_assistant_collection(self) -> None:
        (call,) = self.scenario.vector_store.calls
        self.assertEqual(call["collection"], f"assistant-{ASSISTANT}")
        self.assertEqual(call["limit"], 30)
        self.assertFalse(call["sparse_vector"].is_empty)

    def test_without_history_the_question_is_not_rewritten(self) -> None:
        self.assertEqual(self.result.rewritten_query, "Quanto duram as ferias?")
        self.assertEqual(len(self.scenario.llm.calls), 1)


class MinimumScoreTestCase(unittest.TestCase):
    """CT-14: fallback quando nenhum candidato atinge a nota minima (RN-17)."""

    def test_no_candidate_reaches_the_minimum_score(self) -> None:
        scenario = Scenario(results=[[hit("doc-1", "Outro assunto.", score=0.49)]])
        result = scenario.ask("Qual a cotacao do dolar?")
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.used_context_chunks, 0)
        self.assertEqual(result.citations, ())
        self.assertIn(FALLBACK, result.assistant_message.content)
        self.assertEqual(scenario.llm.calls, [])

    def test_score_equal_to_the_minimum_is_accepted(self) -> None:
        scenario = Scenario(results=[[hit("doc-1", "No limite.", score=0.5)]])
        result = scenario.ask("Pergunta?")
        self.assertFalse(result.fallback_used)

    def test_empty_base_uses_fallback_without_reranking_or_llm(self) -> None:
        scenario = Scenario(results=[[]])
        result = scenario.ask("Pergunta?")
        self.assertTrue(result.fallback_used)
        self.assertEqual(scenario.reranker.calls, [])
        self.assertEqual(scenario.llm.calls, [])
        self.assertEqual(len(scenario.conversations.messages), 2)

    def test_only_chunks_above_the_minimum_reach_the_llm(self) -> None:
        scenario = Scenario(
            results=[[hit("doc-1", "Fraco.", score=0.9), hit("doc-2", "Forte.", index=1)]],
            scores={"Fraco.": 0.1, "Forte.": 0.8},
        )
        result = scenario.ask("Pergunta?")
        (call,) = scenario.llm.calls
        self.assertEqual([chunk.text for chunk in call["context_chunks"]], ["Forte."])
        self.assertEqual(result.citations[0].document_id, "doc-2")

    def test_top_k_lowers_the_number_of_chunks_for_one_question(self) -> None:
        hits = [hit("doc-1", f"Trecho {index}.", index=index) for index in range(8)]
        scenario = Scenario(results=[hits])
        scenario.ask("Pergunta?", top_k=2)
        (call,) = scenario.llm.calls
        self.assertEqual(len(call["context_chunks"]), 2)

    def test_top_k_never_exceeds_the_configured_top_n(self) -> None:
        hits = [hit("doc-1", f"Trecho {index}.", index=index) for index in range(8)]
        scenario = Scenario(results=[hits])
        scenario.ask("Pergunta?", top_k=20)
        (call,) = scenario.llm.calls
        self.assertEqual(len(call["context_chunks"]), 5)

    def test_only_the_top_n_reranked_candidates_are_considered(self) -> None:
        hits = [hit("doc-1", f"Trecho {index}.", index=index) for index in range(8)]
        scenario = Scenario(
            results=[hits],
            settings=RetrievalSettings(top_n=3),
        )
        scenario.ask("Pergunta?")
        (call,) = scenario.llm.calls
        self.assertEqual(len(call["context_chunks"]), 3)


class CitationValidationTestCase(unittest.TestCase):
    """CT-15: resposta sem citacao valida vira fallback (RN-18)."""

    def _ask(self, answer: str):
        scenario = Scenario(
            results=[[hit("doc-1", "Trecho unico.")]],
            answers=(answer,),
        )
        return scenario, scenario.ask("Pergunta?")

    def test_answer_without_marker_is_replaced(self) -> None:
        scenario, result = self._ask("Resposta sem nenhuma fonte.")
        self.assertTrue(result.fallback_used)
        self.assertIn(FALLBACK, result.assistant_message.content)
        self.assertEqual(result.citations, ())
        self.assertEqual(result.used_context_chunks, 0)
        self.assertEqual(scenario.conversations.messages[-1].citations, ())

    def test_marker_pointing_to_unknown_chunk_is_replaced(self) -> None:
        _, result = self._ask("Resposta com fonte inexistente [2].")
        self.assertTrue(result.fallback_used)

    def test_empty_answer_is_replaced(self) -> None:
        _, result = self._ask("   ")
        self.assertTrue(result.fallback_used)

    def test_valid_marker_is_kept_and_unknown_marker_is_removed(self) -> None:
        scenario, result = self._ask("Afirmacao [1]. Outra [7]. Mais [1, 9].")
        self.assertFalse(result.fallback_used)
        self.assertEqual([item.number for item in result.citations], [1])
        self.assertEqual(
            result.assistant_message.content,
            "Afirmacao [1]. Outra. Mais [1].",
        )
        self.assertEqual(
            scenario.conversations.messages[-1].content,
            "Afirmacao [1]. Outra. Mais [1].",
        )


class HistoryBudgetTestCase(unittest.TestCase):
    """CT-16: historico truncado, preservando as mensagens recentes (RN-19)."""

    def _scenario(self, budget: int) -> Scenario:
        scenario = Scenario(
            results=[[hit("doc-1", "Trecho.")]],
            answers=("pergunta reescrita", "Resposta [1]."),
            settings=RetrievalSettings(history_token_budget=budget),
        )
        scenario.conversations.add_turn("um dois tres quatro", "cinco seis sete")
        scenario.conversations.add_turn("oito nove", "dez onze doze")
        return scenario

    def test_only_recent_messages_within_the_budget_are_sent(self) -> None:
        scenario = self._scenario(budget=6)
        scenario.ask("Nova pergunta?")
        history = scenario.llm.calls[-1]["conversation_history"]
        self.assertEqual(
            [message.content for message in history],
            ["oito nove", "dez onze doze"],
        )

    def test_history_within_the_budget_is_sent_in_full(self) -> None:
        scenario = self._scenario(budget=12)
        scenario.ask("Nova pergunta?")
        history = scenario.llm.calls[-1]["conversation_history"]
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0].content, "um dois tres quatro")

    def test_message_larger_than_the_budget_leaves_no_history(self) -> None:
        scenario = self._scenario(budget=2)
        result = scenario.ask("Nova pergunta?")
        # Sem historico nao ha reescrita: a unica chamada e a de geracao.
        self.assertEqual(len(scenario.llm.calls), 1)
        self.assertEqual(scenario.llm.calls[0]["conversation_history"], [])
        self.assertEqual(result.rewritten_query, "Nova pergunta?")

    def test_current_question_is_not_part_of_the_history(self) -> None:
        scenario = self._scenario(budget=100)
        scenario.ask("Nova pergunta?")
        history = scenario.llm.calls[-1]["conversation_history"]
        self.assertNotIn("Nova pergunta?", [item.content for item in history])


class ContextBudgetTestCase(unittest.TestCase):
    """RF-39: o contexto respeita o orcamento, na ordem de relevancia."""

    def test_chunks_beyond_the_budget_are_left_out(self) -> None:
        scenario = Scenario(
            results=[
                [
                    hit("doc-1", "um dois tres", score=0.9),
                    hit("doc-2", "quatro cinco seis", score=0.8),
                    hit("doc-3", "sete", score=0.7),
                ]
            ],
            settings=RetrievalSettings(context_token_budget=5),
        )
        scenario.ask("Pergunta?")
        (call,) = scenario.llm.calls
        self.assertEqual(
            [chunk.text for chunk in call["context_chunks"]], ["um dois tres"]
        )

    def test_budget_smaller_than_the_first_chunk_uses_fallback(self) -> None:
        scenario = Scenario(
            results=[[hit("doc-1", "um dois tres")]],
            settings=RetrievalSettings(context_token_budget=2),
        )
        result = scenario.ask("Pergunta?")
        self.assertTrue(result.fallback_used)
        self.assertEqual(scenario.llm.calls, [])


class QuestionRewriteTestCase(unittest.TestCase):
    """CT-17: pergunta de continuacao reescrita com o tema do historico."""

    def setUp(self) -> None:
        self.scenario = Scenario(
            results=[[hit("doc-1", "Estagiarios tem recesso de trinta dias.")]],
            answers=(
                "Qual a politica de ferias para estagiarios?\n",
                "O recesso e de trinta dias [1].",
            ),
        )
        self.scenario.conversations.add_turn(
            "Qual a politica de ferias?",
            "Sao trinta dias por ano [1].",
        )
        self.result = self.scenario.ask("e para estagiarios?")

    def test_search_query_mentions_the_topic_of_the_conversation(self) -> None:
        self.assertEqual(
            self.result.rewritten_query,
            "Qual a politica de ferias para estagiarios?",
        )
        query, _ = self.scenario.reranker.calls[0]
        self.assertIn("ferias", query)
        self.assertIn("estagiarios", query)

    def test_rewrite_call_receives_the_history_and_no_context(self) -> None:
        rewrite_call, answer_call = self.scenario.llm.calls
        self.assertIn(REWRITE_INSTRUCTION, rewrite_call["prompt"])
        self.assertIn("e para estagiarios?", rewrite_call["prompt"])
        self.assertEqual(rewrite_call["context_chunks"], [])
        self.assertEqual(len(rewrite_call["conversation_history"]), 2)
        self.assertEqual(len(answer_call["context_chunks"]), 1)

    def test_answer_and_stored_message_keep_the_original_question(self) -> None:
        answer_call = self.scenario.llm.calls[1]
        self.assertIn("Pergunta: e para estagiarios?", answer_call["prompt"])
        self.assertEqual(self.result.user_message.content, "e para estagiarios?")

    def test_empty_rewrite_falls_back_to_the_original_question(self) -> None:
        scenario = Scenario(
            results=[[hit("doc-1", "Trecho.")]],
            answers=("  ", "Resposta [1]."),
        )
        scenario.conversations.add_turn("Pergunta anterior?", "Resposta anterior.")
        result = scenario.ask("e agora?")
        self.assertEqual(result.rewritten_query, "e agora?")


class FailingRewriteLLM(ScriptedLLM):
    """Falha na reescrita (chamada sem contexto) e responde na geracao."""

    def __init__(self, error: Exception) -> None:
        super().__init__("Resposta [1].")
        self._error = error

    def generate(self, *, prompt, context_chunks, conversation_history) -> str:
        if not context_chunks:
            self.calls.append({"prompt": prompt, "context_chunks": []})
            raise self._error
        return super().generate(
            prompt=prompt,
            context_chunks=context_chunks,
            conversation_history=conversation_history,
        )


class RewriteFailureTestCase(unittest.TestCase):
    """Falha do LLM na reescrita nao interrompe a pergunta."""

    def _ask(self, error: Exception, results: list[list[SearchResult]]):
        scenario = Scenario(results=results)
        scenario.llm = FailingRewriteLLM(error)
        scenario.use_case = ChatWithAssistantUseCase(
            assistant_repository=InMemoryAssistantRepository(),
            conversation_repository=scenario.conversations,
            context_retriever=build_retriever(scenario.vector_store),
            answer_generator=GroundedAnswerGenerator(llm_gateway=scenario.llm),
            token_counter=WordTokenCounter(),
            access_control=scenario.access.control,
        )
        scenario.conversations.add_turn("Pergunta anterior?", "Resposta anterior.")
        with self.assertLogs(
            "src.application.services.grounded_answer", level="WARNING"
        ) as logs:
            result = scenario.ask("e para estagiarios?")
        self.assertIn("chat.rewrite.failed", logs.output[0])
        return scenario, result

    def test_provider_error_falls_back_to_the_original_question(self) -> None:
        scenario, result = self._ask(
            RuntimeError("LLM provider is unreachable."),
            [[hit("doc-1", "Trecho.")]],
        )
        self.assertEqual(result.rewritten_query, "e para estagiarios?")
        self.assertFalse(result.fallback_used)
        self.assertEqual(len(scenario.llm.calls), 2)

    def test_unconfigured_llm_still_allows_the_fallback_answer(self) -> None:
        _, result = self._ask(
            ValueError("Global LLM API key is not configured."),
            [[hit("doc-1", "Outro assunto.", score=0.1)]],
        )
        self.assertTrue(result.fallback_used)
        self.assertIn(FALLBACK, result.assistant_message.content)


class InputValidationTestCase(unittest.TestCase):
    def test_empty_question_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Scenario(results=[]).ask("   ")

    def test_unknown_conversation_is_reported(self) -> None:
        with self.assertRaises(ConversationNotFoundError):
            Scenario(results=[]).ask("Pergunta?", conversation_id="outra")


if __name__ == "__main__":
    unittest.main()
