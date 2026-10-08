from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from access_support import ADMIN, AccessHarness
from src.api.dependencies import (
    get_assistant_repository,
    get_document_indexer,
    get_document_repository,
    get_embedding_gateway,
    get_file_storage,
    get_ingestion_job_queue,
    get_max_file_bytes,
    get_reindex_job_repository,
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
from src.application.use_cases import ProcessNextIngestionJobUseCase
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
    DocumentStatus,
    IngestionJob,
    IngestionJobStatus,
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

    def list_by_assistant(
        self,
        assistant_id: AssistantId,
        owner_user_id: str,
    ) -> list[Conversation]:
        return [
            conversation
            for conversation in self.items
            if conversation.assistant_id == assistant_id
            and conversation.owner_user_id == owner_user_id
        ]


class InMemoryDocumentRepository:
    def __init__(self) -> None:
        self.items: dict[str, Document] = {}

    def save(self, document: Document) -> Document:
        self.items[document.id.value] = document
        return document

    def get_by_id(self, document_id: DocumentId) -> Document | None:
        return self.items.get(document_id.value)

    def list_by_assistant(self, assistant_id: AssistantId) -> list[Document]:
        return [
            item
            for item in self.items.values()
            if item.assistant_id == assistant_id
            and item.status is not DocumentStatus.REPLACED
        ]

    def find_by_hash(
        self,
        assistant_id: AssistantId,
        content_hash: str,
    ) -> Document | None:
        return next(
            (
                item
                for item in self.list_by_assistant(assistant_id)
                if item.content_hash == content_hash
            ),
            None,
        )

    def delete(self, document_id: DocumentId) -> bool:
        return self.items.pop(document_id.value, None) is not None


class InMemoryJobQueue:
    """Fila do worker; ``complete``, ``retry`` e ``fail`` gravam o documento."""

    def __init__(self, documents: InMemoryDocumentRepository) -> None:
        self.documents = documents
        self.jobs: dict[str, IngestionJob] = {}

    def enqueue(self, job: IngestionJob) -> IngestionJob:
        self.jobs[job.id] = job
        return job

    def reserve_next(self, now: datetime) -> IngestionJob | None:
        for job in self.jobs.values():
            if (
                job.status is IngestionJobStatus.PENDING
                and self.documents.get_by_id(job.document_id) is not None
            ):
                self.jobs[job.id] = job.reserve(now)
                return self.jobs[job.id]
        return None

    def list_expired(self, reserved_before: datetime) -> list[IngestionJob]:
        return []

    def complete(self, job, document, replaced=None) -> None:
        self.jobs[job.id] = job
        self.documents.save(document)
        if replaced is not None:
            self.documents.save(replaced)

    def retry(self, job, document) -> None:
        self.jobs[job.id] = job
        self.documents.save(document)

    def fail(self, job, document) -> None:
        self.jobs[job.id] = job
        self.documents.save(document)


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

    def delete(self, storage_key: str) -> None:
        self.files.pop(storage_key, None)


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
        self.group_updates: list[tuple[str, str, frozenset[str]]] = []
        self.deleted_documents: list[str] = []

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
        *,
        user_groups: frozenset[str] | None,
    ) -> list[SearchResult]:
        return []

    def set_document_groups(
        self,
        collection_name: CollectionName,
        document_id: DocumentId,
        groups: frozenset[str],
    ) -> None:
        self.group_updates.append(
            (collection_name.value, document_id.value, groups)
        )

    def delete_by_document(
        self, collection_name: CollectionName, document_id: DocumentId
    ) -> None:
        self.deleted_documents.append(document_id.value)
        self.upserts = [
            (name, [chunk for chunk in chunks if chunk.document_id != document_id])
            for name, chunks in self.upserts
        ]

    def set_document_active(
        self,
        collection_name: CollectionName,
        document_id: DocumentId,
        active: bool,
    ) -> None:
        self.upserts = [
            (
                name,
                [
                    replace(chunk, active=active)
                    if chunk.document_id == document_id
                    else chunk
                    for chunk in chunks
                ],
            )
            for name, chunks in self.upserts
        ]

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
        # As rotas exigem identidade; aqui quem chama e um administrador.
        self.access = AccessHarness(self.app, ADMIN)

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
            Conversation(
                id=ConversationId("conv-1"),
                assistant_id=assistant_id,
                owner_user_id=ADMIN.id,
            ),
            Conversation(
                id=ConversationId("conv-2"),
                assistant_id=assistant_id,
                owner_user_id=ADMIN.id,
            ),
            Conversation(
                id=ConversationId("conv-other"),
                assistant_id=AssistantId("assistant-2"),
                owner_user_id=ADMIN.id,
            ),
            # RN-24: nem o administrador ve a conversa de outra pessoa.
            Conversation(
                id=ConversationId("conv-alheia"),
                assistant_id=assistant_id,
                owner_user_id="outro-usuario",
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
        self.job_repository = job_repository
        file_storage = InMemoryFileStorage()
        overrides = self.app.dependency_overrides
        overrides[get_assistant_repository] = lambda: assistant_repository
        overrides[get_document_repository] = lambda: document_repository
        overrides[get_vector_store_gateway] = lambda: vector_store
        overrides[get_reindex_job_repository] = lambda: job_repository
        overrides[get_file_storage] = lambda: file_storage
        overrides[get_document_indexer] = _fake_document_indexer
        overrides[get_embedding_gateway] = FakeEmbeddingGateway
        overrides[get_max_file_bytes] = lambda: max_file_bytes
        self.queue = InMemoryJobQueue(document_repository)
        overrides[get_ingestion_job_queue] = lambda: self.queue
        self.worker = ProcessNextIngestionJobUseCase(
            job_queue=self.queue,
            document_repository=document_repository,
            vector_store_gateway=vector_store,
            document_indexer=_fake_document_indexer(),
            file_storage=file_storage,
            reindex_job_repository=job_repository,
            access_control=self.access.control,
        )
        return document_repository, vector_store

    def _run_worker(self) -> None:
        """Faz o papel do servico ``worker`` ate a fila esvaziar."""
        while self.worker.execute() is not None:
            pass

    def test_ingest_document_endpoint_accepts_text_file_and_metadata(self) -> None:
        """RF-48: responde 202 com o documento pendente; o worker indexa."""
        document_repository, vector_store = self._override_indexing()

        with TestClient(self.app) as client:
            response = client.post(
                "/assistants/assistant-1/documents",
                files={"file": ("manual.txt", b"Conteudo principal", "text/plain")},
                data={"metadata": '{"source":"qa","team":"ops"}'},
            )
            self.assertEqual(response.status_code, 202)
            payload = response.json()
            self.assertEqual(payload["assistant_id"], "assistant-1")
            self.assertEqual(payload["source_name"], "manual.txt")
            self.assertEqual(payload["status"], "pendente")
            self.assertEqual(payload["version"], 1)
            self.assertEqual(payload["chunk_count"], 0)
            self.assertEqual(payload["size_bytes"], len(b"Conteudo principal"))
            self.assertEqual(vector_store.upserts, [])

            self._run_worker()
            current = client.get(f"/documents/{payload['id']}")

        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json()["status"], "indexado")
        self.assertGreaterEqual(current.json()["chunk_count"], 1)
        self.assertIn("assistant-assistant-1-v1", vector_store.collections)
        self.assertEqual(
            vector_store.aliases,
            {"assistant-assistant-1": "assistant-assistant-1-v1"},
        )
        stored = next(iter(document_repository.items.values()))
        self.assertEqual(
            stored.metadata,
            DocumentMetadata(values={"source": "qa", "team": "ops"}),
        )
        self.assertIsNotNone(stored.storage_key)
        (_, chunks), = vector_store.upserts
        self.assertTrue(all(chunk.active for chunk in chunks))

    def test_ingest_document_endpoint_restricts_chunks_from_the_start(self) -> None:
        """D8 da SPEC-004: grupos no envio gravam os trechos ja restritos."""
        document_repository, vector_store = self._override_indexing()

        with TestClient(self.app) as client:
            response = client.post(
                "/assistants/assistant-1/documents",
                files={"file": ("manual.txt", b"Conteudo principal", "text/plain")},
                data={"groups": '["/diretoria", "rh"]'},
            )
            invalid = client.post(
                "/assistants/assistant-1/documents",
                files={"file": ("outro.txt", b"Outro conteudo", "text/plain")},
                data={"groups": "diretoria"},
            )
        self._run_worker()

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["groups"], ["diretoria", "rh"])
        (_, chunks), = vector_store.upserts
        self.assertTrue(all(chunk.allowed_groups == ("diretoria", "rh") for chunk in chunks))
        stored = next(iter(document_repository.items.values()))
        self.assertEqual(
            self.access.permissions.get_document_groups(stored.id),
            frozenset({"diretoria", "rh"}),
        )
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(len(document_repository.items), 1)

    def test_duplicate_upload_reports_the_existing_document(self) -> None:
        """RN-26: 409 com o documento ja enviado; nada e gravado."""
        document_repository, _ = self._override_indexing()
        upload = {"file": ("manual.txt", b"Conteudo principal", "text/plain")}

        with TestClient(self.app) as client:
            first = client.post("/assistants/assistant-1/documents", files=upload)
            again = client.post(
                "/assistants/assistant-1/documents",
                files={"file": ("copia.txt", b"Conteudo principal", "text/plain")},
            )

        self.assertEqual(again.status_code, 409)
        detail = again.json()["detail"]
        self.assertEqual(detail["code"], "duplicate_document")
        self.assertEqual(detail["document_id"], first.json()["id"])
        self.assertEqual(detail["source_name"], "manual.txt")
        self.assertEqual(len(document_repository.items), 1)

    def test_document_lifecycle_routes(self) -> None:
        """RF-50, RF-51, RF-54: excluir, substituir e reprocessar."""
        document_repository, vector_store = self._override_indexing()

        with TestClient(self.app) as client:
            created = client.post(
                "/assistants/assistant-1/documents",
                files={"file": ("manual.txt", b"Versao um.", "text/plain")},
            ).json()
            self._run_worker()
            reprocess_indexed = client.post(f"/documents/{created['id']}/reprocess")
            replaced = client.put(
                f"/documents/{created['id']}/content",
                files={"file": ("manual-v2.txt", b"Versao dois.", "text/plain")},
            )
            self._run_worker()
            listed = client.get("/assistants/assistant-1/documents")
            new_id = replaced.json()["id"]
            deleted = client.delete(f"/documents/{new_id}")
            after_delete = client.get(f"/documents/{new_id}")
            unknown = client.delete("/documents/nao-existe")

        self.assertEqual(reprocess_indexed.status_code, 409)
        self.assertEqual(replaced.status_code, 202)
        self.assertEqual(replaced.json()["version"], 2)
        self.assertEqual(replaced.json()["replaces_document_id"], created["id"])
        self.assertEqual(
            [(item["id"], item["status"]) for item in listed.json()],
            [(new_id, "indexado")],
        )
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(after_delete.status_code, 404)
        self.assertEqual(unknown.status_code, 404)
        self.assertIn(new_id, vector_store.deleted_documents)
        self.assertEqual(
            document_repository.items[created["id"]].status, DocumentStatus.REPLACED
        )

    def test_failed_document_is_reprocessed_from_the_original(self) -> None:
        document_repository, _ = self._override_indexing()

        with TestClient(self.app) as client:
            created = client.post(
                "/assistants/assistant-1/documents",
                files={"file": ("vazio.txt", b"   ", "text/plain")},
            ).json()
            self._run_worker()
            failed = client.get(f"/documents/{created['id']}").json()
            again = client.post(f"/documents/{created['id']}/reprocess")

        self.assertEqual(failed["status"], "falhou")
        self.assertTrue(failed["failure_reason"])
        self.assertEqual(again.status_code, 202)
        self.assertEqual(again.json()["status"], "pendente")

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

    def test_reindex_endpoint_only_records_the_request_for_the_worker(self) -> None:
        """PC-D4: a API registra o pedido; o worker reserva e executa."""
        self._override_indexing()

        with TestClient(self.app) as client:
            response = client.post("/assistants/assistant-1/reindex")
            conflict = client.post("/assistants/assistant-1/reindex")

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["target_collection"], "assistant-assistant-1-v1")
        job = self.job_repository.get_by_id(payload["id"])
        self.assertIsNotNone(job)
        self.assertEqual(job.attempts, 0)
        self.assertIsNone(job.lease_expires_at)
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
            self._run_worker()
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
