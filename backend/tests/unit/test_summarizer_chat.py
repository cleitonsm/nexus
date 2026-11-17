"""SPEC-018: conversa com o resumidor (RN-59, RN-61, RN-65, D33, T3).

Parte do CT-145: roteamento antes do grafo, resposta sem LLM nas rotas de
finalidade, progresso e resumo gravado, resumo sob medida sobre os
mini-resumos e pergunta pontual com escopo pessoal.
"""

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
from summarizer_doubles import Documents, Summaries

from src.application.services import GroundedAnswerGenerator, SummarizerChat
from src.application.use_cases import ChatWithAssistantInput, ChatWithAssistantUseCase
from src.domain import (
    SUMMARIZER_ASSISTANT_ID,
    AccessDeniedError,
    Assistant,
    AssistantName,
    ChatMessage,
    Conversation,
    ConversationId,
    Document,
    DocumentId,
    DocumentStatus,
    DocumentSummary,
    DocumentSummarySection,
    SummarizerCapabilities,
    SummaryStage,
    TokenUsage,
)

USER = make_user("ana")
CONVERSATION = ConversationId("c1")
NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)


class ScopedVectorStore(ScriptedVectorStore):
    def hybrid_search(self, *args, personal_scope=None, **kwargs):
        results = super().hybrid_search(*args, **kwargs)
        self.calls[-1]["personal_scope"] = personal_scope
        return results


class Assistants:
    def get_by_id(self, assistant_id):
        return Assistant(
            id=SUMMARIZER_ASSISTANT_ID,
            name=AssistantName("Resumidor de documentos"),
            system_kind="document_summarizer",
        )


class Conversations:
    def __init__(self) -> None:
        self.messages: list[ChatMessage] = []

    def get_by_id(self, conversation_id):
        return Conversation(
            id=CONVERSATION, assistant_id=SUMMARIZER_ASSISTANT_ID, owner_user_id=USER.id
        )

    def save_message(self, message: ChatMessage) -> ChatMessage:
        self.messages.append(message)
        return message

    def list_messages(self, conversation_id):
        return list(self.messages)


class CountingUsage:
    def __init__(self) -> None:
        self.checks = 0
        self.records: list[dict[str, object]] = []

    def check(self, user) -> None:
        self.checks += 1

    def record(self, user, **kwargs) -> None:
        self.records.append(kwargs)


class Scenario:
    def __init__(self, *, answers=("Resposta [1].",), results=None) -> None:
        self.documents = Documents()
        self.summaries = Summaries()
        self.conversations = Conversations()
        self.vector_store = ScopedVectorStore(results or [])
        self.llm = ScriptedLLM(*answers, usage=TokenUsage(input_tokens=100, output_tokens=20))
        self.usage = CountingUsage()
        access = AccessFixture()
        self.use_case = ChatWithAssistantUseCase(
            assistant_repository=Assistants(),
            conversation_repository=self.conversations,
            context_retriever=build_retriever(self.vector_store, reranker=ScriptedReranker()),
            answer_generator=GroundedAnswerGenerator(llm_gateway=self.llm),
            token_counter=WordTokenCounter(),
            access_control=access.control,
            usage_governance=self.usage,  # type: ignore[arg-type]
            summarizer=SummarizerChat(
                documents=self.documents,
                summaries=self.summaries,
                capabilities=SummarizerCapabilities(formats=(".pdf", ".docx"), max_bytes=25 * 1024 * 1024),
            ),
        )

    def with_document(self, status: DocumentStatus, stage: SummaryStage | None, **summary) -> Document:
        document = self.documents.save(
            Document(
                id=DocumentId("d1"),
                assistant_id=SUMMARIZER_ASSISTANT_ID,
                source_name="contrato-ficticio.pdf",
                content_hash="h",
                status=status,
                owner_user_id=USER.id,
                conversation_id=CONVERSATION,
                expires_at=NOW + timedelta(days=30),
            )
        )
        if stage is not None:
            self.summaries.create(DocumentSummary(document_id=document.id, stage=stage, **summary))
        return document

    def ask(self, question: str):
        return self.use_case.execute(
            ChatWithAssistantInput(user=USER, conversation_id=CONVERSATION.value, question=question)
        )


class SummarizerChatTestCase(unittest.TestCase):
    def test_without_document_explains_without_llm_or_quota(self) -> None:
        """RN-61 item 1, RF-119 e RNF-38."""
        scenario = Scenario()
        result = scenario.ask("quais arquivos você aceita?")
        self.assertIn("anexe", result.assistant_message.content.lower())
        self.assertIn(".pdf", result.assistant_message.content)
        self.assertEqual(scenario.llm.calls, [])
        self.assertEqual((scenario.usage.checks, scenario.usage.records), (0, []))
        self.assertEqual([m.role.value for m in scenario.conversations.messages], ["user", "assistant"])

    def test_progress_before_indexing(self) -> None:
        scenario = Scenario()
        scenario.with_document(DocumentStatus.PROCESSING, SummaryStage.EXTRACTING)
        result = scenario.ask("qual o prazo?")
        self.assertIn("Estou lendo", result.assistant_message.content)
        self.assertEqual(scenario.llm.calls, [])

    def test_stored_summary_is_returned_without_llm(self) -> None:
        """RNF-37: o resumo gravado, com as citacoes gravadas."""
        scenario = Scenario()
        scenario.with_document(DocumentStatus.INDEXED, SummaryStage.READY, content="## Visão geral\nResumo [1].")
        result = scenario.ask("resuma o documento")
        self.assertEqual(result.assistant_message.content, "## Visão geral\nResumo [1].")
        self.assertEqual(scenario.llm.calls, [])
        self.assertEqual(scenario.usage.records, [])

    def test_tailored_summary_uses_only_the_mini_summaries(self) -> None:
        """D33 e RN-65: uma chamada, sem busca, contada como pergunta."""
        scenario = Scenario(answers=("- Ponto executivo [2].",))
        document = scenario.with_document(DocumentStatus.INDEXED, SummaryStage.READY, content="Resumo")
        for position, title in enumerate(("Cláusula 1", "Cláusula 2")):
            scenario.summaries.save_section(
                DocumentSummarySection(
                    document_id=document.id, position=position, title=title,
                    input_tokens=5_000, content=f"mini {position}", page_start=position + 1,
                )
            )
        result = scenario.ask("resuma em 3 tópicos para um diretor")
        self.assertEqual(len(scenario.llm.calls), 1)
        self.assertEqual(scenario.vector_store.calls, [])
        sent = scenario.llm.calls[0]["context_chunks"]
        self.assertEqual([chunk.text for chunk in sent], ["mini 0", "mini 1"])
        citation = result.assistant_message.citations[0]
        self.assertEqual((citation.section_path, citation.page, citation.chunk_id), ("Cláusula 2", 2, "d1:section:1"))
        self.assertEqual(scenario.usage.checks, 1)
        self.assertEqual(len(scenario.usage.records), 1)

    def test_question_searches_with_the_personal_scope(self) -> None:
        """RN-59 e D34: perguntas liberadas durante o resumo."""
        scenario = Scenario(results=[[hit("d1", "A vigência é de 12 meses.")]])
        scenario.with_document(DocumentStatus.INDEXED, SummaryStage.SUMMARIZING)
        result = scenario.ask("qual o prazo de vigência?")
        call = scenario.vector_store.calls[0]
        self.assertEqual(call["collection"], "assistant-system-document-summarizer")
        self.assertEqual(call["personal_scope"].owner_user_id, "ana")
        self.assertEqual(call["personal_scope"].conversation_id, CONVERSATION)
        self.assertFalse(result.fallback_used)
        self.assertEqual(scenario.vector_store.article_calls, [])
        self.assertEqual(scenario.usage.checks, 1)

    def test_summarizer_search_without_scope_is_refused(self) -> None:
        """T2: a camada de aplicacao tambem falha fechada."""
        retriever = build_retriever(ScopedVectorStore([]))
        with self.assertRaises(AccessDeniedError):
            retriever.search(SUMMARIZER_ASSISTANT_ID, "prazo", user_groups=frozenset())

    def test_streaming_delivers_the_direct_answer(self) -> None:
        scenario = Scenario()
        scenario.with_document(DocumentStatus.INDEXED, SummaryStage.READY, content="Resumo pronto.")
        events = list(
            scenario.use_case.start_stream(
                ChatWithAssistantInput(user=USER, conversation_id=CONVERSATION.value, question="resumo")
            )
        )
        self.assertEqual([event.kind for event in events], ["delta", "done"])
        self.assertEqual(events[0].text, "Resumo pronto.")



class RuntimeResolutionTestCase(unittest.TestCase):
    """Revisao de 2026-10-30: rotas sem LLM nao resolvem credencial (RNF-37)."""

    def test_only_llm_routes_resolve_the_runtime(self) -> None:
        from src.application.services import RetrievalSettings

        calls: list[str] = []

        class Runtime:
            retrieval = RetrievalSettings()
            usage_model = "m"
            usage_pricing = None

            def __init__(self, llm) -> None:
                self.llm_gateway = llm

            def log_fields(self) -> dict[str, object]:
                return {}

        scenario = Scenario(answers=("- Ponto [1].",))
        scenario.use_case._runtime_resolver = lambda assistant: calls.append("x") or Runtime(scenario.llm)
        scenario.ask("quais arquivos você aceita?")
        self.assertEqual(calls, [])
        document = scenario.with_document(DocumentStatus.INDEXED, SummaryStage.READY, content="Resumo")
        scenario.summaries.save_section(
            DocumentSummarySection(document_id=document.id, position=0, title="Parte",
                                   input_tokens=10, content="mini", page_start=None)
        )
        scenario.ask("resuma")
        self.assertEqual(calls, [])
        scenario.ask("resuma em 2 tópicos")
        self.assertEqual(calls, ["x"])

if __name__ == "__main__":
    unittest.main()
