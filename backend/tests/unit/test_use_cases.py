import unittest

from src.application.use_cases import (
    ChatWithAssistantInput,
    ChatWithAssistantUseCase,
    CreateAssistantInput,
    CreateAssistantUseCase,
    GetGlobalApiKeyStatusUseCase,
    GetGlobalApiKeyValueUseCase,
    IngestDocumentInput,
    IngestDocumentUseCase,
    ListAssistantsUseCase,
    ListConversationsInput,
    ListConversationsUseCase,
    RegisterConversationInput,
    RegisterConversationUseCase,
    SaveGlobalApiKeyInput,
    SaveGlobalApiKeyUseCase,
)
from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    ChatMessage,
    CollectionName,
    Conversation,
    ConversationId,
    Document,
    DocumentId,
    MessageId,
    MessageRole,
    SearchResult,
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

    def delete(self, assistant_id: AssistantId) -> bool:
        return self.items.pop(assistant_id.value, None) is not None


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self.items: dict[str, Conversation] = {}
        self.messages: dict[str, list[ChatMessage]] = {}

    def save(self, conversation: Conversation) -> Conversation:
        self.items[conversation.id.value] = conversation
        self.messages.setdefault(
            conversation.id.value,
            list(conversation.messages),
        )
        return conversation

    def get_by_id(self, conversation_id: ConversationId) -> Conversation | None:
        conversation = self.items.get(conversation_id.value)
        if conversation is None:
            return None
        return Conversation(
            id=conversation.id,
            assistant_id=conversation.assistant_id,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=tuple(
                sorted(
                    self.messages.get(conversation_id.value, []),
                    key=lambda item: item.created_at,
                )
            ),
        )

    def list_by_assistant(self, assistant_id: AssistantId) -> list[Conversation]:
        conversations = [
            self.get_by_id(ConversationId(conversation.id.value))
            for conversation in self.items.values()
            if conversation.assistant_id == assistant_id
        ]
        return [
            conversation
            for conversation in conversations
            if conversation is not None
        ]

    def save_message(self, message: ChatMessage) -> ChatMessage:
        conversation = self.items.get(message.conversation_id.value)
        if conversation is None:
            raise ValueError("conversation not found")
        self.messages.setdefault(message.conversation_id.value, []).append(message)
        self.items[message.conversation_id.value] = Conversation(
            id=conversation.id,
            assistant_id=conversation.assistant_id,
            created_at=conversation.created_at,
            updated_at=message.created_at,
            messages=tuple(self.messages[message.conversation_id.value]),
        )
        return message

    def list_messages(self, conversation_id: ConversationId) -> list[ChatMessage]:
        return list(self.messages.get(conversation_id.value, []))

    def delete(self, conversation_id: ConversationId) -> bool:
        deleted = self.items.pop(conversation_id.value, None) is not None
        self.messages.pop(conversation_id.value, None)
        return deleted


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
        self.search_results: dict[str, list[SearchResult]] = {}

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

    def search(self, *args, **kwargs) -> list[SearchResult]:
        collection_name = kwargs["collection_name"].value
        limit = kwargs["limit"]
        return self.search_results.get(collection_name, [])[:limit]

    def delete_collection(self, collection_name: CollectionName) -> None:
        self.collections.pop(collection_name.value, None)
        self.search_results.pop(collection_name.value, None)


class FakeLLMGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str], list[ChatMessage]]] = []

    def generate(
        self,
        *,
        prompt: str,
        context_chunks: list[str],
        conversation_history: list[ChatMessage],
    ) -> str:
        self.calls.append((prompt, context_chunks, conversation_history))
        return f"Resposta com base em {len(context_chunks)} chunks"


class InMemorySecretSettingsRepository:
    def __init__(self) -> None:
        self.items: dict[str, str] = {}

    def set_encrypted_value(
        self,
        *,
        key_name: str,
        encrypted_value: str,
    ) -> None:
        self.items[key_name] = encrypted_value

    def get_encrypted_value(self, *, key_name: str) -> str | None:
        return self.items.get(key_name)


class FakeSecretCipher:
    def encrypt(self, plaintext: str) -> str:
        return f"enc::{plaintext}"

    def decrypt(self, ciphertext: str) -> str:
        return ciphertext.replace("enc::", "", 1)


class UseCasesTestCase(unittest.TestCase):
    def test_save_global_api_key_use_case_encrypts_and_persists_secret(
        self,
    ) -> None:
        repository = InMemorySecretSettingsRepository()
        use_case = SaveGlobalApiKeyUseCase(
            secret_repository=repository,
            secret_cipher=FakeSecretCipher(),
        )

        result = use_case.execute(
            SaveGlobalApiKeyInput(api_key="  sk-test-123  ")
        )

        self.assertTrue(result.configured)
        self.assertEqual(
            repository.get_encrypted_value(key_name="global_llm_api_key"),
            "enc::sk-test-123",
        )

    def test_get_global_api_key_use_cases_report_status_and_decrypt_value(
        self,
    ) -> None:
        repository = InMemorySecretSettingsRepository()
        repository.set_encrypted_value(
            key_name="global_llm_api_key",
            encrypted_value="enc::sk-stored-456",
        )

        status_result = GetGlobalApiKeyStatusUseCase(
            secret_repository=repository
        ).execute()
        value_result = GetGlobalApiKeyValueUseCase(
            secret_repository=repository,
            secret_cipher=FakeSecretCipher(),
        ).execute()

        self.assertTrue(status_result.configured)
        self.assertEqual(value_result, "sk-stored-456")

    def test_create_assistant_use_case_creates_and_returns_dto(self) -> None:
        repo = InMemoryAssistantRepository()
        use_case = CreateAssistantUseCase(repository=repo)

        created = use_case.execute(
            CreateAssistantInput(
                assistant_id="assistant-abc",
                name="Compliance",
                description="Regras internas",
                initial_prompt="Aja como especialista em compliance.",
            )
        )

        self.assertEqual(created.id, "assistant-abc")
        self.assertEqual(created.name, "Compliance")
        self.assertEqual(created.initial_prompt, "Aja como especialista em compliance.")
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

    def test_list_conversations_use_case_returns_assistant_history(self) -> None:
        repo = InMemoryConversationRepository()
        register_use_case = RegisterConversationUseCase(repository=repo)
        register_use_case.execute(
            RegisterConversationInput(
                conversation_id="conv-1",
                assistant_id="assistant-1",
            )
        )
        register_use_case.execute(
            RegisterConversationInput(
                conversation_id="conv-2",
                assistant_id="assistant-1",
            )
        )
        register_use_case.execute(
            RegisterConversationInput(
                conversation_id="conv-3",
                assistant_id="assistant-2",
            )
        )

        use_case = ListConversationsUseCase(repository=repo)
        result = use_case.execute(
            ListConversationsInput(assistant_id="assistant-1")
        )

        self.assertEqual(len(result.conversations), 2)
        self.assertEqual(
            {item.id for item in result.conversations},
            {"conv-1", "conv-2"},
        )

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

    def test_chat_with_assistant_use_case_runs_rag_flow_with_langgraph(
        self,
    ) -> None:
        conversation_repo = InMemoryConversationRepository()
        conversation_repo.save(
            Conversation(
                id=ConversationId("conv-chat"),
                assistant_id=AssistantId("assistant-1"),
            )
        )
        assistant_repo = InMemoryAssistantRepository()
        assistant_repo.save(
            Assistant(
                id=AssistantId("assistant-1"),
                name=AssistantName("Juridico"),
                initial_prompt=(
                    "Aja como um especialista em questoes juridicas e use a "
                    "documentacao RAG como fonte de verdade."
                ),
            )
        )
        vector_store = SpyVectorStoreGateway()
        vector_store.search_results["assistant-assistant-1"] = [
            SearchResult(
                chunk_id="chunk-1",
                document_id=DocumentId("doc-1"),
                score=0.91,
                text="Trecho sobre politica de reembolso",
            )
        ]
        llm_gateway = FakeLLMGateway()
        use_case = ChatWithAssistantUseCase(
            assistant_repository=assistant_repo,
            conversation_repository=conversation_repo,
            embedding_gateway=FakeEmbeddingGateway(),
            vector_store_gateway=vector_store,
            llm_gateway=llm_gateway,
        )

        result = use_case.execute(
            ChatWithAssistantInput(
                conversation_id="conv-chat",
                question="Qual a politica de reembolso?",
                top_k=3,
            )
        )

        self.assertEqual(result.conversation_id, "conv-chat")
        self.assertEqual(result.user_message.role, MessageRole.USER.value)
        self.assertEqual(
            result.assistant_message.role,
            MessageRole.ASSISTANT.value,
        )
        self.assertEqual(result.used_context_chunks, 1)
        self.assertFalse(result.fallback_used)
        self.assertEqual(len(llm_gateway.calls), 1)
        prompt, chunks, history = llm_gateway.calls[0]
        self.assertIn("Qual a politica de reembolso?", prompt)
        self.assertIn("especialista em questoes juridicas", prompt)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(history), 0)
        saved_messages = conversation_repo.list_messages(
            ConversationId("conv-chat")
        )
        self.assertEqual(len(saved_messages), 2)

    def test_chat_with_assistant_use_case_sends_previous_history_to_llm(
        self,
    ) -> None:
        conversation_repo = InMemoryConversationRepository()
        conversation_repo.save(
            Conversation(
                id=ConversationId("conv-history"),
                assistant_id=AssistantId("assistant-1"),
            )
        )
        assistant_repo = InMemoryAssistantRepository()
        assistant_repo.save(
            Assistant(
                id=AssistantId("assistant-1"),
                name=AssistantName("Historico"),
            )
        )
        conversation_repo.save_message(
            ChatMessage(
                id=MessageId("msg-1"),
                conversation_id=ConversationId("conv-history"),
                role=MessageRole.USER,
                content="Primeira pergunta",
            )
        )
        conversation_repo.save_message(
            ChatMessage(
                id=MessageId("msg-2"),
                conversation_id=ConversationId("conv-history"),
                role=MessageRole.ASSISTANT,
                content="Primeira resposta",
            )
        )
        vector_store = SpyVectorStoreGateway()
        vector_store.search_results["assistant-assistant-1"] = [
            SearchResult(
                chunk_id="chunk-1",
                document_id=DocumentId("doc-1"),
                score=0.95,
                text="Contexto valido",
            )
        ]
        llm_gateway = FakeLLMGateway()
        use_case = ChatWithAssistantUseCase(
            assistant_repository=assistant_repo,
            conversation_repository=conversation_repo,
            embedding_gateway=FakeEmbeddingGateway(),
            vector_store_gateway=vector_store,
            llm_gateway=llm_gateway,
        )

        use_case.execute(
            ChatWithAssistantInput(
                conversation_id="conv-history",
                question="Segunda pergunta",
            )
        )

        self.assertEqual(len(llm_gateway.calls), 1)
        _, _, history = llm_gateway.calls[0]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].content, "Primeira pergunta")
        self.assertEqual(history[1].content, "Primeira resposta")

    def test_chat_with_assistant_use_case_returns_fallback_when_no_context(
        self,
    ) -> None:
        conversation_repo = InMemoryConversationRepository()
        conversation_repo.save(
            Conversation(
                id=ConversationId("conv-no-context"),
                assistant_id=AssistantId("assistant-2"),
            )
        )
        assistant_repo = InMemoryAssistantRepository()
        assistant_repo.save(
            Assistant(
                id=AssistantId("assistant-2"),
                name=AssistantName("Sem contexto"),
            )
        )
        llm_gateway = FakeLLMGateway()
        use_case = ChatWithAssistantUseCase(
            assistant_repository=assistant_repo,
            conversation_repository=conversation_repo,
            embedding_gateway=FakeEmbeddingGateway(),
            vector_store_gateway=SpyVectorStoreGateway(),
            llm_gateway=llm_gateway,
        )

        result = use_case.execute(
            ChatWithAssistantInput(
                conversation_id="conv-no-context",
                question="Existe cobertura para evento X?",
            )
        )

        self.assertTrue(result.fallback_used)
        self.assertEqual(result.used_context_chunks, 0)
        self.assertEqual(len(llm_gateway.calls), 0)
        self.assertIn(
            "Nao encontrei contexto suficiente",
            result.assistant_message.content,
        )


if __name__ == "__main__":
    unittest.main()
