"""CT-147 (SPEC-018): rotas do resumidor pela API.

Repositorios em memoria (os dubles do CT-143) e identidade dublada, como o
CT-127; nao precisa do Keycloak, do banco nem do Qdrant. Execute dentro do
container do backend.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))

from access_support import AccessHarness, member  # noqa: E402
from ingestion_doubles import InMemoryIngestionJobQueue  # noqa: E402
from summarizer_doubles import Conversations, Documents, Indexer, Storage, Summaries  # noqa: E402

from src.api.dependencies import (  # noqa: E402
    get_conversation_repository,
    get_document_indexer,
    get_document_repository,
    get_document_summary_repository,
    get_file_storage,
    get_ingestion_job_queue,
    get_max_file_bytes,
)
from src.api.routes.summarizer import router  # noqa: E402
from src.domain import (  # noqa: E402
    SUMMARIZER_ASSISTANT_ID,
    AssistantId,
    Conversation,
    ConversationId,
    SummaryStage,
)

ANA = member("ana", "rh")
BRUNO = member("bruno", "rh")
MAX_BYTES = 1024


class SummarizerApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(router)
        self.access = AccessHarness(self.app, ANA)
        self.conversations = Conversations()
        self.documents = Documents()
        self.summaries = Summaries()
        self.queue = InMemoryIngestionJobQueue(self.documents)
        overrides = self.app.dependency_overrides
        overrides[get_conversation_repository] = lambda: self.conversations
        overrides[get_document_repository] = lambda: self.documents
        overrides[get_document_summary_repository] = lambda: self.summaries
        overrides[get_file_storage] = Storage
        overrides[get_document_indexer] = Indexer
        overrides[get_ingestion_job_queue] = lambda: self.queue
        overrides[get_max_file_bytes] = lambda: MAX_BYTES
        self.client = TestClient(self.app)
        for conversation_id, owner, assistant in (
            ("c1", "ana", SUMMARIZER_ASSISTANT_ID),
            ("c2", "ana", SUMMARIZER_ASSISTANT_ID),
            ("rh", "ana", AssistantId("rh")),
        ):
            self.conversations.save(
                Conversation(id=ConversationId(conversation_id), assistant_id=assistant, owner_user_id=owner)
            )

    def upload(self, conversation: str = "c1", name: str = "contrato.pdf", content: bytes = b"texto"):
        return self.client.post(
            f"/conversations/{conversation}/document", files={"file": (name, content, "application/pdf")}
        )

    def test_info_without_document(self) -> None:
        body = self.client.get("/summarizer").json()
        self.assertEqual(body["assistant_id"], SUMMARIZER_ASSISTANT_ID.value)
        self.assertEqual((body["max_tokens"], body["daily_limit"], body["retention_days"]), (40000, 10, 30))
        self.assertIn(".docx", body["formats"])
        self.assertIn("Resumidor de documentos", body["welcome_markdown"])

    def test_upload_status_and_summary(self) -> None:
        response = self.upload()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["stage"], "enviado")
        status = self.client.get("/conversations/c1/document")
        self.assertEqual((status.status_code, status.json()["stage"]), (200, "enviado"))
        not_ready = self.client.get("/conversations/c1/summary")
        self.assertEqual((not_ready.status_code, not_ready.json()["code"]), (409, "summary_not_ready"))
        document = self.documents.get_personal_by_conversation(ConversationId("c1"))
        self.summaries.complete(document.id, content="Resumo", citations=(), prompt_version="v", model="m")
        summary = self.client.get("/conversations/c1/summary")
        self.assertEqual((summary.status_code, summary.json()["content"]), (200, "Resumo"))

    def test_errors_with_stable_codes(self) -> None:
        self.assertEqual(self.upload().status_code, 202)
        cases = (
            (self.upload("c1", "outro.pdf"), 409, "conversation_document_exists"),
            (self.upload("rh"), 409, "not_summarizer_conversation"),
            (self.upload("c2", "planilha.xlsx"), 415, "unsupported_format"),
            (self.upload("c2", content=b"x" * (MAX_BYTES + 1)), 413, "payload_too_large"),
            (self.client.get("/conversations/c2/document"), 404, "summary_document_not_found"),
            (self.client.post("/conversations/c1/summary/retry"), 409, "summary_not_failed"),
        )
        for response, status_code, code in cases:
            with self.subTest(code=code):
                self.assertEqual((response.status_code, response.json()["code"]), (status_code, code))

    def test_someone_elses_conversation_is_404(self) -> None:
        """RN-24 e RN-58: nem o administrador ve o documento pessoal."""
        self.upload()
        for user in (BRUNO, member("root", role="nexus-admin")):
            self.access.user = user
            with self.subTest(user=user.id):
                self.assertEqual(self.client.get("/conversations/c1/document").status_code, 404)
                self.assertEqual(self.client.get("/conversations/c1/summary").status_code, 404)
                self.assertEqual(self.upload().status_code, 404)

    def test_daily_limit_is_429(self) -> None:
        for index in range(10):
            conversation = f"q{index}"
            self.conversations.save(
                Conversation(id=ConversationId(conversation), assistant_id=SUMMARIZER_ASSISTANT_ID, owner_user_id="ana")
            )
            self.assertEqual(self.upload(conversation).status_code, 202)
        response = self.upload("c2")
        self.assertEqual((response.status_code, response.json()["code"]), (429, "summary_daily_limit"))

    def test_retry_after_summary_failure(self) -> None:
        self.upload()
        document = self.documents.get_personal_by_conversation(ConversationId("c1"))
        self.documents.save(
            document.start_processing(1).mark_indexed(embedding_model="m", pipeline_version="p", chunk_count=1)
        )
        self.summaries.fail(document.id, "summary_failed")
        response = self.client.post("/conversations/c1/summary/retry")
        self.assertEqual((response.status_code, response.json()["stage"]), (202, "resumindo"))
        self.assertIs(self.summaries.get(document.id).stage, SummaryStage.SUMMARIZING)


class SystemAssistantRoutesTestCase(unittest.TestCase):
    """RN-55 pela API: a exclusao do resumidor responde 409 ao administrador."""

    def test_delete_is_409(self) -> None:
        from src.api.routes.assistants import router as assistants_router

        app = FastAPI()
        app.include_router(assistants_router)
        AccessHarness(app, member("root", role="nexus-admin"))
        app.dependency_overrides[get_document_repository] = Documents
        app.dependency_overrides[get_file_storage] = Storage
        response = TestClient(app).delete(f"/assistants/{SUMMARIZER_ASSISTANT_ID.value}")
        self.assertEqual((response.status_code, response.json()["code"]), (409, "system_assistant_readonly"))


if __name__ == "__main__":
    unittest.main()
