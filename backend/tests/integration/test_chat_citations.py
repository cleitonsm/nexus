"""CT-20 (SPEC-20261007-003): citacoes devolvidas pela API e persistidas.

A primeira classe usa repositorios em memoria; a segunda exige o PostgreSQL
do Compose. Execute dentro do container do backend.
"""

from __future__ import annotations

import unittest
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from access_support import AccessHarness, member
from src.api.dependencies import (
    get_answer_generator,
    get_assistant_repository,
    get_context_retriever,
    get_conversation_repository,
    get_token_counter,
)
from src.api.routes import conversations_router
from src.application.services import (
    ContextRetriever,
    GroundedAnswerGenerator,
    RetrievalSettings,
)
from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    ChatMessage,
    Citation,
    CollectionName,
    Conversation,
    ConversationId,
    DocumentId,
    IndexOutdatedError,
    MessageId,
    MessageRole,
    SearchResult,
    SparseVector,
)
from src.infrastructure.embeddings import Bm25SparseEmbeddingGateway
from src.infrastructure.llm import FakeContextAwareLLM

ASSISTANT = AssistantId("assistant-1")
CONVERSATION = ConversationId("conv-1")
OWNER = member("user-1", "rh")


class InMemoryAssistantRepository:
    def get_by_id(self, assistant_id: AssistantId) -> Assistant | None:
        return Assistant(id=ASSISTANT, name=AssistantName("RH"))


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self.messages: list[ChatMessage] = []

    def get_by_id(self, conversation_id: ConversationId) -> Conversation | None:
        if conversation_id != CONVERSATION:
            return None
        return Conversation(
            id=CONVERSATION,
            assistant_id=ASSISTANT,
            messages=tuple(self.messages),
            owner_user_id=OWNER.id,
        )

    def save_message(self, message: ChatMessage) -> ChatMessage:
        self.messages.append(message)
        return message

    def list_messages(self, conversation_id: ConversationId) -> list[ChatMessage]:
        return list(self.messages)


class FakeEmbeddingGateway:
    model_name = "fake"
    dimension = 1

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0]


class FakeVectorStore:
    def __init__(self, results: list[SearchResult], outdated: bool = False) -> None:
        self._results = results
        self._outdated = outdated

    def hybrid_search(
        self,
        collection_name: CollectionName,
        dense_vector: list[float],
        sparse_vector: SparseVector,
        limit: int,
        payload_filter: dict[str, str] | None = None,
        *,
        user_groups: frozenset[str] | None,
    ) -> list[SearchResult]:
        if self._outdated:
            raise IndexOutdatedError("the assistant index is incompatible.")
        return self._results[:limit]


class KeepScoreReranker:
    model_name = "fake-reranker"

    def rerank(self, query: str, candidates: list[SearchResult]) -> list[SearchResult]:
        return sorted(candidates, key=lambda item: item.score, reverse=True)


class WordTokenCounter:
    max_tokens = 128

    def count(self, text: str) -> int:
        return len(text.split())


def _hit(score: float) -> SearchResult:
    return SearchResult(
        chunk_id="doc-1:2",
        document_id=DocumentId("doc-1"),
        score=score,
        text="As ferias sao de trinta dias.",
        source_name="politica.pdf",
        section_path="Ferias > Duracao",
        page=3,
    )


class ChatCitationsApiTestCase(unittest.TestCase):
    def _client(
        self,
        results: list[SearchResult],
        outdated: bool = False,
    ) -> TestClient:
        app = FastAPI()
        app.include_router(conversations_router)
        AccessHarness(app, OWNER).link_assistant(ASSISTANT.value, "rh")
        conversations = InMemoryConversationRepository()
        retriever = ContextRetriever(
            embedding_gateway=FakeEmbeddingGateway(),
            sparse_embedding_gateway=Bm25SparseEmbeddingGateway(),
            vector_store_gateway=FakeVectorStore(results, outdated),
            reranker_gateway=KeepScoreReranker(),
            settings=RetrievalSettings(),
        )
        overrides = app.dependency_overrides
        overrides[get_assistant_repository] = InMemoryAssistantRepository
        overrides[get_conversation_repository] = lambda: conversations
        overrides[get_context_retriever] = lambda: retriever
        overrides[get_answer_generator] = lambda: GroundedAnswerGenerator(
            llm_gateway=FakeContextAwareLLM()
        )
        overrides[get_token_counter] = WordTokenCounter
        return TestClient(app)

    def test_chat_returns_citations_and_conversation_keeps_them(self) -> None:
        with self._client([_hit(0.9)]) as client:
            response = client.post(
                "/conversations/conv-1/chat",
                json={"question": "Quanto duram as ferias?", "top_k": 4},
            )
            detail = client.get("/conversations/conv-1")

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertFalse(body["fallback_used"])
        self.assertEqual(body["rewritten_query"], "Quanto duram as ferias?")
        expected = {
            "number": 1,
            "document_id": "doc-1",
            "chunk_id": "doc-1:2",
            "source_name": "politica.pdf",
            "section_path": "Ferias > Duracao",
            "page": 3,
            "score": 0.9,
            "excerpt": "As ferias sao de trinta dias.",
        }
        self.assertEqual(body["citations"], [expected])
        self.assertEqual(body["assistant_message"]["citations"], [expected])
        self.assertEqual(body["user_message"]["citations"], [])

        self.assertEqual(detail.status_code, 200)
        user_message, assistant_message = detail.json()["messages"]
        self.assertEqual(user_message["citations"], [])
        self.assertEqual(assistant_message["citations"], [expected])

    def test_out_of_scope_question_returns_fallback_without_citations(self) -> None:
        with self._client([_hit(0.2)]) as client:
            response = client.post(
                "/conversations/conv-1/chat",
                json={"question": "Qual a cotacao do dolar?"},
            )
        body = response.json()
        self.assertEqual(response.status_code, 201)
        self.assertTrue(body["fallback_used"])
        self.assertEqual(body["citations"], [])
        self.assertEqual(body["used_context_chunks"], 0)

    def test_top_k_limits_the_chunks_of_one_question(self) -> None:
        hits = [
            SearchResult(
                chunk_id=f"doc-1:{index}",
                document_id=DocumentId("doc-1"),
                score=0.9 - index / 100,
                text=f"Trecho {index}.",
            )
            for index in range(6)
        ]
        with self._client(hits) as client:
            limited = client.post(
                "/conversations/conv-1/chat",
                json={"question": "Pergunta?", "top_k": 2},
            )
            above = client.post(
                "/conversations/conv-1/chat",
                json={"question": "Pergunta?", "top_k": 20},
            )
        self.assertEqual(limited.json()["used_context_chunks"], 2)
        self.assertEqual(above.json()["used_context_chunks"], 5)

    def test_incompatible_index_is_reported_as_conflict(self) -> None:
        with self._client([], outdated=True) as client:
            response = client.post(
                "/conversations/conv-1/chat",
                json={"question": "Pergunta?"},
            )
        self.assertEqual(response.status_code, 409)


def _database_session():
    """Sessao no PostgreSQL com as migracoes aplicadas, ou None."""
    try:
        from sqlalchemy import text

        from src.infrastructure.database import SessionLocal, run_migrations

        run_migrations()
        session = SessionLocal()
        session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - banco indisponivel pula o teste
        return None
    return session


class MessageCitationsPersistenceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        session = _database_session()
        if session is None:
            self.skipTest("PostgreSQL indisponivel")
        from src.infrastructure.database import (
            PostgresAssistantRepository,
            PostgresConversationRepository,
        )

        self.session = session
        self.assistants = PostgresAssistantRepository(session=session)
        self.conversations = PostgresConversationRepository(session=session)
        self.assistant_id = AssistantId(f"teste-citacoes-{uuid4().hex[:12]}")
        self.conversation_id = ConversationId(str(uuid4()))
        self.assistants.save(
            Assistant(id=self.assistant_id, name=AssistantName("Citacoes"))
        )
        self.conversations.save(
            Conversation(id=self.conversation_id, assistant_id=self.assistant_id)
        )
        self.addCleanup(session.close)
        self.addCleanup(self.assistants.delete, self.assistant_id)

    def _save(self, role: MessageRole, citations: tuple[Citation, ...]) -> None:
        self.conversations.save_message(
            ChatMessage(
                id=MessageId(str(uuid4())),
                conversation_id=self.conversation_id,
                role=role,
                content="conteudo",
                citations=citations,
            )
        )

    def test_citations_round_trip_through_the_messages_table(self) -> None:
        citation = Citation(
            number=2,
            document_id=DocumentId("doc-1"),
            chunk_id="doc-1:2",
            source_name="política.pdf",
            excerpt="As férias são de trinta dias.",
            section_path="Férias > Duração",
            page=3,
            score=0.87,
        )
        self._save(MessageRole.USER, ())
        self._save(MessageRole.ASSISTANT, (citation,))
        self.session.expire_all()

        user_message, assistant_message = self.conversations.list_messages(
            self.conversation_id
        )
        self.assertEqual(user_message.citations, ())
        self.assertEqual(assistant_message.citations, (citation,))
        loaded = self.conversations.get_by_id(self.conversation_id)
        self.assertEqual(loaded.messages[-1].citations, (citation,))


if __name__ == "__main__":
    unittest.main()
