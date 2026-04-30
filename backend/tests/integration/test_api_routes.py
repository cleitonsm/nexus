from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import (
    get_assistant_repository,
    get_document_repository,
    get_embedding_gateway,
    get_secret_cipher,
    get_secret_settings_repository,
    get_vector_store_gateway,
    get_conversation_repository,
)
from src.api.routes import admin_router, assistants_router, documents_router
from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    CollectionName,
    Conversation,
    ConversationId,
    Document,
    DocumentId,
    DocumentMetadata,
    SearchResult,
    VectorChunk,
)


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


class InMemoryAssistantRepository:
    def __init__(self, assistants: list[Assistant]) -> None:
        self.items = {assistant.id.value: assistant for assistant in assistants}

    def get_by_id(self, assistant_id: AssistantId) -> Assistant | None:
        return self.items.get(assistant_id.value)


class InMemoryConversationRepository:
    def __init__(self, conversations: list[Conversation]) -> None:
        self.items = conversations

    def list_by_assistant(self, assistant_id: AssistantId) -> list[Conversation]:
        return [
            conversation
            for conversation in self.items
            if conversation.assistant_id == assistant_id
        ]


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
        return [[1.0, 2.0] for _ in texts]


class SpyVectorStoreGateway:
    def __init__(self) -> None:
        self.collections: dict[str, int] = {}
        self.upserts: list[tuple[str, list[VectorChunk]]] = []

    def ensure_collection(
        self, collection_name: CollectionName, vector_size: int
    ) -> None:
        self.collections[collection_name.value] = vector_size

    def upsert_chunks(
        self, collection_name: CollectionName, chunks: list[VectorChunk]
    ) -> None:
        self.upserts.append((collection_name.value, chunks))

    def search(
        self,
        collection_name: CollectionName,
        query_vector: list[float],
        limit: int,
    ) -> list[SearchResult]:
        return []


class ApiRoutesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(admin_router)
        self.app.include_router(assistants_router)
        self.app.include_router(documents_router)
        self.app.dependency_overrides.clear()

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_admin_api_key_endpoints_store_encrypted_value(self) -> None:
        repository = InMemorySecretSettingsRepository()
        self.app.dependency_overrides[get_secret_settings_repository] = (
            lambda: repository
        )
        self.app.dependency_overrides[get_secret_cipher] = FakeSecretCipher

        with TestClient(self.app) as client:
            status_before = client.get("/admin/api-key/status")
            self.assertEqual(status_before.status_code, 200)
            self.assertEqual(status_before.json(), {"configured": False})

            save_response = client.post(
                "/admin/api-key",
                json={"api_key": "sk-live-xyz"},
            )
            self.assertEqual(save_response.status_code, 201)
            self.assertEqual(save_response.json(), {"configured": True})

            status_after = client.get("/admin/api-key/status")
            self.assertEqual(status_after.status_code, 200)
            self.assertEqual(status_after.json(), {"configured": True})

        self.assertEqual(
            repository.items["global_llm_api_key"],
            "enc::sk-live-xyz",
        )

    def test_list_assistant_conversations_returns_only_assistant_history(self) -> None:
        assistant_id = AssistantId("assistant-1")
        assistants = [
            Assistant(id=assistant_id, name=AssistantName("Operacoes")),
            Assistant(id=AssistantId("assistant-2"), name=AssistantName("Financeiro")),
        ]
        conversations = [
            Conversation(id=ConversationId("conv-1"), assistant_id=assistant_id),
            Conversation(id=ConversationId("conv-2"), assistant_id=assistant_id),
            Conversation(
                id=ConversationId("conv-other"),
                assistant_id=AssistantId("assistant-2"),
            ),
        ]
        self.app.dependency_overrides[get_assistant_repository] = lambda: InMemoryAssistantRepository(
            assistants
        )
        self.app.dependency_overrides[get_conversation_repository] = lambda: InMemoryConversationRepository(
            conversations
        )

        with TestClient(self.app) as client:
            response = client.get("/assistants/assistant-1/conversations")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 2)
        self.assertEqual({item["id"] for item in payload}, {"conv-1", "conv-2"})

    def test_ingest_document_endpoint_accepts_text_file_and_metadata(self) -> None:
        assistant_id = AssistantId("assistant-1")
        assistant_repository = InMemoryAssistantRepository(
            [Assistant(id=assistant_id, name=AssistantName("Atendimento"))]
        )
        document_repository = InMemoryDocumentRepository()
        vector_store = SpyVectorStoreGateway()

        self.app.dependency_overrides[get_assistant_repository] = lambda: assistant_repository
        self.app.dependency_overrides[get_document_repository] = lambda: document_repository
        self.app.dependency_overrides[get_embedding_gateway] = FakeEmbeddingGateway
        self.app.dependency_overrides[get_vector_store_gateway] = lambda: vector_store

        with TestClient(self.app) as client:
            response = client.post(
                "/assistants/assistant-1/documents",
                files={"file": ("manual.txt", b"Conteudo principal", "text/plain")},
                data={"metadata": '{"source":"qa","team":"ops"}'},
            )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["assistant_id"], "assistant-1")
        self.assertEqual(payload["source_name"], "manual.txt")
        self.assertGreaterEqual(payload["chunk_count"], 1)
        self.assertEqual(payload["embedding_dimension"], 2)
        self.assertIn("assistant-assistant-1", vector_store.collections)
        self.assertEqual(len(document_repository.items), 1)
        stored = next(iter(document_repository.items.values()))
        self.assertEqual(
            stored.metadata,
            DocumentMetadata(values={"source": "qa", "team": "ops"}),
        )


if __name__ == "__main__":
    unittest.main()
