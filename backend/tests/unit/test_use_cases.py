import unittest

from src.application.use_cases import (
    CreateAssistantInput,
    CreateAssistantUseCase,
    IngestDocumentInput,
    IngestDocumentUseCase,
    ListAssistantsUseCase,
    RegisterConversationInput,
    RegisterConversationUseCase,
)
from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    CollectionName,
    Conversation,
    ConversationId,
    Document,
    VectorChunk,
)


class InMemoryAssistantRepository:
    def __init__(self) -> None:
        self.items: dict[str, Assistant] = {}

    def save(self, assistant: Assistant) -> Assistant:
        self.items[assistant.id.value] = assistant
        return assistant

    def list_all(self) -> list[Assistant]:
        return list(self.items.values())

    def get_by_id(self, assistant_id: AssistantId) -> Assistant | None:
        return self.items.get(assistant_id.value)


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self.items: dict[str, Conversation] = {}

    def save(self, conversation: Conversation) -> Conversation:
        self.items[conversation.id.value] = conversation
        return conversation

    def get_by_id(self, conversation_id: ConversationId) -> Conversation | None:
        return self.items.get(conversation_id.value)

    def save_message(
        self,
        message,
    ):  # pragma: no cover - not used in this stage
        raise NotImplementedError

    def list_messages(
        self,
        conversation_id: ConversationId,
    ):  # pragma: no cover - not used
        raise NotImplementedError


class InMemoryDocumentRepository:
    def __init__(self) -> None:
        self.items: dict[str, Document] = {}

    def save(self, document: Document) -> Document:
        self.items[document.id.value] = document
        return document

    def list_by_assistant(self, assistant_id: AssistantId) -> list[Document]:
        return [
            item
            for item in self.items.values()
            if item.assistant_id == assistant_id
        ]


class FakeEmbeddingGateway:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [
            [float(index + 1), float(index + 2)]
            for index, _ in enumerate(texts)
        ]


class SpyVectorStoreGateway:
    def __init__(self) -> None:
        self.collections: dict[str, int] = {}
        self.upserts: list[tuple[str, list[VectorChunk]]] = []

    def ensure_collection(
        self,
        collection_name: CollectionName,
        vector_size: int,
    ) -> None:
        self.collections[collection_name.value] = vector_size

    def upsert_chunks(
        self,
        collection_name: CollectionName,
        chunks: list[VectorChunk],
    ) -> None:
        self.upserts.append((collection_name.value, chunks))

    def search(self, *args, **kwargs):  # pragma: no cover - not used in this stage
        raise NotImplementedError


class UseCasesTestCase(unittest.TestCase):
    def test_create_assistant_use_case_creates_and_returns_dto(self) -> None:
        repo = InMemoryAssistantRepository()
        use_case = CreateAssistantUseCase(repository=repo)

        created = use_case.execute(
            CreateAssistantInput(
                assistant_id="assistant-abc",
                name="Compliance",
                description="Regras internas",
            )
        )

        self.assertEqual(created.id, "assistant-abc")
        self.assertEqual(created.name, "Compliance")
        self.assertEqual(len(repo.list_all()), 1)

    def test_list_assistants_use_case_maps_entities_to_dtos(self) -> None:
        repo = InMemoryAssistantRepository()
        repo.save(
            Assistant(
                id=AssistantId("assistant-1"),
                name=AssistantName("Financeiro"),
            )
        )
        repo.save(
            Assistant(
                id=AssistantId("assistant-2"),
                name=AssistantName("Juridico"),
            )
        )
        use_case = ListAssistantsUseCase(repository=repo)

        items = use_case.execute()

        self.assertEqual(len(items), 2)
        self.assertEqual(
            {item.id for item in items},
            {"assistant-1", "assistant-2"},
        )

    def test_register_conversation_use_case_persists_conversation(self) -> None:
        repo = InMemoryConversationRepository()
        use_case = RegisterConversationUseCase(repository=repo)

        result = use_case.execute(
            RegisterConversationInput(
                conversation_id="conv-1",
                assistant_id="assistant-1",
            )
        )

        self.assertEqual(result.conversation.id, "conv-1")
        self.assertEqual(result.conversation.assistant_id, "assistant-1")
        self.assertIsNotNone(repo.get_by_id(ConversationId("conv-1")))

    def test_ingest_document_use_case_creates_collection_per_assistant(
        self,
    ) -> None:
        document_repo = InMemoryDocumentRepository()
        embedding_gateway = FakeEmbeddingGateway()
        vector_store = SpyVectorStoreGateway()
        use_case = IngestDocumentUseCase(
            document_repository=document_repo,
            embedding_gateway=embedding_gateway,
            vector_store_gateway=vector_store,
        )

        first_result = use_case.execute(
            IngestDocumentInput(
                assistant_id="assistant-1",
                document_id="doc-1",
                source_name="manual-a.txt",
                content="Linha um\nLinha dois\nLinha tres",
                metadata={"source": "teste"},
                chunk_size=12,
                chunk_overlap=3,
            )
        )
        second_result = use_case.execute(
            IngestDocumentInput(
                assistant_id="assistant-2",
                document_id="doc-2",
                source_name="manual-b.txt",
                content="Outro documento para outro assistente",
            )
        )

        self.assertEqual(first_result.collection_name, "assistant-assistant-1")
        self.assertEqual(second_result.collection_name, "assistant-assistant-2")
        self.assertIn("assistant-assistant-1", vector_store.collections)
        self.assertIn("assistant-assistant-2", vector_store.collections)
        self.assertEqual(vector_store.collections["assistant-assistant-1"], 2)
        self.assertEqual(vector_store.collections["assistant-assistant-2"], 2)

        first_upsert = vector_store.upserts[0]
        self.assertEqual(first_upsert[0], "assistant-assistant-1")
        self.assertGreaterEqual(len(first_upsert[1]), 2)
        self.assertEqual(first_upsert[1][0].assistant_id.value, "assistant-1")
        self.assertEqual(first_upsert[1][0].document_id.value, "doc-1")
        self.assertEqual(first_upsert[1][0].source_name, "manual-a.txt")

        stored_document = document_repo.items["doc-1"]
        self.assertEqual(stored_document.metadata.values["source"], "teste")

    def test_ingest_document_rejects_empty_content(self) -> None:
        use_case = IngestDocumentUseCase(
            document_repository=InMemoryDocumentRepository(),
            embedding_gateway=FakeEmbeddingGateway(),
            vector_store_gateway=SpyVectorStoreGateway(),
        )

        with self.assertRaises(ValueError):
            use_case.execute(
                IngestDocumentInput(
                    assistant_id="assistant-1",
                    source_name="empty.txt",
                    content="   ",
                )
            )


if __name__ == "__main__":
    unittest.main()
