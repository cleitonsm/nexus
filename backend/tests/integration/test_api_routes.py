from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import (
    get_assistant_repository,
    get_document_indexer,
    get_document_repository,
    get_embedding_gateway,
    get_file_storage,
    get_max_file_bytes,
    get_reindex_job_repository,
    get_reindex_runner,
    get_secret_cipher,
    get_secret_settings_repository,
    get_vector_store_gateway,
    get_conversation_repository,
)
from src.api.routes import (
    admin_router,
    assistants_router,
    documents_router,
    index_router,
)
from src.application.services import DocumentIndexer
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
    ReindexJob,
    SearchResult,
    SparseVector,
    VectorChunk,
)
from src.infrastructure.chunking import StructuralDocumentChunker
from src.infrastructure.documents import SupportedDocumentExtractor
from src.infrastructure.embeddings import Bm25SparseEmbeddingGateway


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
    model_name = "fake-model"
    dimension = 2

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 2.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 2.0]


class WordTokenCounter:
    max_tokens = 128

    def count(self, text: str) -> int:
        return len(text.split()) + 2


def _fake_document_indexer() -> DocumentIndexer:
    return DocumentIndexer(
        extractor=SupportedDocumentExtractor(),
        chunker=StructuralDocumentChunker(
            token_counter=WordTokenCounter(),
            max_tokens=128,
            overlap_sentences=1,
            max_prefix_tokens=32,
        ),
        embedding_gateway=FakeEmbeddingGateway(),
        sparse_embedding_gateway=Bm25SparseEmbeddingGateway(),
    )


class InMemoryFileStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def save(
        self,
        *,
        assistant_id: AssistantId,
        document_id: DocumentId,
        filename: str,
        content: bytes,
    ) -> str:
        key = f"{assistant_id.value}/{document_id.value}"
        self.files[key] = content
        return key

    def load(self, storage_key: str) -> bytes:
        return self.files[storage_key]


class InMemoryReindexJobRepository:
    def __init__(self) -> None:
        self.items: dict[str, ReindexJob] = {}

    def save(self, job: ReindexJob) -> ReindexJob:
        self.items[job.id] = job
        return job

    def get_by_id(self, job_id: str) -> ReindexJob | None:
        return self.items.get(job_id)

    def get_latest(self, assistant_id: AssistantId) -> ReindexJob | None:
        jobs = [
            job for job in self.items.values() if job.assistant_id == assistant_id
        ]
        return jobs[-1] if jobs else None

    def get_running(self, assistant_id: AssistantId) -> ReindexJob | None:
        for job in self.items.values():
            if job.assistant_id == assistant_id and job.is_running:
                return job
        return None

    def list_running(self) -> list[ReindexJob]:
        return [job for job in self.items.values() if job.is_running]


class SpyVectorStoreGateway:
    def __init__(self) -> None:
        self.collections: dict[str, int] = {}
        self.aliases: dict[str, str] = {}
        self.upserts: list[tuple[str, list[VectorChunk]]] = []

    def ensure_collection(
        self, collection_name: CollectionName, vector_size: int
    ) -> None:
        self.collections[collection_name.value] = vector_size

    def upsert_chunks(
        self, collection_name: CollectionName, chunks: list[VectorChunk]
    ) -> None:
        self.upserts.append((collection_name.value, chunks))

    def hybrid_search(
        self,
        collection_name: CollectionName,
        dense_vector: list[float],
        sparse_vector: SparseVector,
        limit: int,
        payload_filter: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        return []

    def delete_collection(self, collection_name: CollectionName) -> None:
        self.collections.pop(collection_name.value, None)

    def collection_exists(self, collection_name: CollectionName) -> bool:
        return collection_name.value in self.collections

    def count_points(self, collection_name: CollectionName) -> int:
        return 0

    def resolve_alias(self, alias: CollectionName) -> CollectionName | None:
        target = self.aliases.get(alias.value)
        return CollectionName(target) if target else None

    def point_alias(
        self, alias: CollectionName, collection_name: CollectionName
    ) -> None:
        self.aliases[alias.value] = collection_name.value


class ApiRoutesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(admin_router)
        self.app.include_router(assistants_router)
        self.app.include_router(documents_router)
        self.app.include_router(index_router)
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

    def _override_indexing(
        self,
        *,
        max_file_bytes: int = 1024,
    ) -> tuple[InMemoryDocumentRepository, SpyVectorStoreGateway]:
        assistant_repository = InMemoryAssistantRepository(
            [Assistant(id=AssistantId("assistant-1"), name=AssistantName("Atendimento"))]
        )
        document_repository = InMemoryDocumentRepository()
        vector_store = SpyVectorStoreGateway()
        job_repository = InMemoryReindexJobRepository()
        file_storage = InMemoryFileStorage()
        self.started_jobs: list[str] = []
        overrides = self.app.dependency_overrides
        overrides[get_assistant_repository] = lambda: assistant_repository
        overrides[get_document_repository] = lambda: document_repository
        overrides[get_vector_store_gateway] = lambda: vector_store
        overrides[get_reindex_job_repository] = lambda: job_repository
        overrides[get_file_storage] = lambda: file_storage
        overrides[get_document_indexer] = _fake_document_indexer
        overrides[get_embedding_gateway] = FakeEmbeddingGateway
        overrides[get_max_file_bytes] = lambda: max_file_bytes
        overrides[get_reindex_runner] = lambda: self.started_jobs.append
        return document_repository, vector_store

    def test_ingest_document_endpoint_accepts_text_file_and_metadata(self) -> None:
        document_repository, vector_store = self._override_indexing()

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
        self.assertEqual(payload["embedding_model"], "fake-model")
        self.assertEqual(payload["collection_name"], "assistant-assistant-1")
        self.assertIn("assistant-assistant-1-v1", vector_store.collections)
        self.assertEqual(
            vector_store.aliases,
            {"assistant-assistant-1": "assistant-assistant-1-v1"},
        )
        self.assertEqual(len(document_repository.items), 1)
        stored = next(iter(document_repository.items.values()))
        self.assertEqual(
            stored.metadata,
            DocumentMetadata(values={"source": "qa", "team": "ops"}),
        )
        self.assertIsNotNone(stored.storage_key)

    def test_ingest_document_endpoint_rejects_file_above_limit(self) -> None:
        document_repository, _ = self._override_indexing(max_file_bytes=8)

        with TestClient(self.app) as client:
            response = client.post(
                "/assistants/assistant-1/documents",
                files={"file": ("manual.txt", b"Conteudo principal", "text/plain")},
            )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(document_repository.items, {})

    def test_ingest_document_endpoint_refuses_outdated_index(self) -> None:
        _, vector_store = self._override_indexing()
        vector_store.collections["assistant-assistant-1"] = 384

        with TestClient(self.app) as client:
            response = client.post(
                "/assistants/assistant-1/documents",
                files={"file": ("manual.txt", b"Conteudo principal", "text/plain")},
            )

        self.assertEqual(response.status_code, 409)

    def test_reindex_endpoint_accepts_and_schedules_background_run(self) -> None:
        self._override_indexing()

        with TestClient(self.app) as client:
            response = client.post("/assistants/assistant-1/reindex")
            conflict = client.post("/assistants/assistant-1/reindex")

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["target_collection"], "assistant-assistant-1-v1")
        self.assertEqual(self.started_jobs, [payload["id"]])
        self.assertEqual(conflict.status_code, 409)

    def test_reindex_endpoint_reports_unknown_assistant(self) -> None:
        self._override_indexing()

        with TestClient(self.app) as client:
            response = client.post("/assistants/nao-existe/reindex")

        self.assertEqual(response.status_code, 404)

    def test_index_status_endpoint_reports_model_and_documents(self) -> None:
        self._override_indexing()

        with TestClient(self.app) as client:
            client.post(
                "/assistants/assistant-1/documents",
                files={"file": ("manual.txt", b"Conteudo principal", "text/plain")},
            )
            response = client.get("/assistants/assistant-1/index-status")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["embedding_model"], "fake-model")
        self.assertEqual(payload["collection_name"], "assistant-assistant-1-v1")
        self.assertFalse(payload["outdated"])
        self.assertEqual(payload["documents_total"], 1)
        self.assertEqual(payload["documents_indexed"], 1)
        self.assertEqual(payload["documents_without_original"], [])
        self.assertIsNone(payload["last_reindex"])


if __name__ == "__main__":
    unittest.main()
