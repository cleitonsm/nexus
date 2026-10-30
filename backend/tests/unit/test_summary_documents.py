"""SPEC-018: casos de uso do resumidor.

CT-142 (acesso e RN-55 nos casos de uso), CT-143 (envio do documento pessoal),
acesso rapido com o cartao fixo (RN-57), exclusao da conversa e limpeza dos
vencidos (RF-120) e a nova tentativa do resumo (RN-64).
"""

from __future__ import annotations

import unittest
from datetime import timedelta

from access_doubles import AccessFixture, admin, curator, make_user
from ingestion_doubles import InMemoryIngestionJobQueue, ManualClock
from summarizer_doubles import Conversations, Documents, Indexer, Storage, Summaries, VectorStore

from src.application.services import PersonalDocumentRemover
from src.application.use_cases.chat_with_assistant import ConversationNotFoundError
from src.application.use_cases.ingest_document import DocumentTooLargeError
from src.application.use_cases.list_assistants import ListAssistantsUseCase
from src.application.use_cases.manage_conversation import (
    ConversationRefInput,
    DeleteConversationUseCase,
)
from src.application.use_cases.manage_home_assistants import (
    GetHomeAssistantsUseCase,
    SetHomeAssistantsInput,
    SetHomeAssistantsUseCase,
)
from src.application.use_cases.summary_documents import (
    GetStoredSummaryUseCase,
    GetSummarizerInfoUseCase,
    GetSummaryDocumentStatusUseCase,
    PurgeExpiredSummaryDocumentsUseCase,
    RetrySummaryUseCase,
    SummaryConversationInput,
    SummaryDocumentNotFoundError,
    UploadSummaryDocumentInput,
    UploadSummaryDocumentUseCase,
)
from src.domain import (
    SUMMARIZER_ASSISTANT_ID,
    SUMMARIZER_COLLECTION,
    AccessDeniedError,
    Assistant,
    AssistantId,
    AssistantName,
    AuditAction,
    Conversation,
    ConversationDocumentExistsError,
    ConversationId,
    DocumentStatus,
    HomeAssistantSelection,
    HomeAssistantsValidationError,
    IngestionJobKind,
    NotSummarizerConversationError,
    SummaryDailyLimitError,
    SummaryNotFailedError,
    SummaryNotReadyError,
    SummaryStage,
    SystemAssistantReadonlyError,
)

ANA = make_user("ana")
BRUNO = make_user("bruno")
MAX_BYTES = 25 * 1024 * 1024
SUMMARIZER = Assistant(
    id=SUMMARIZER_ASSISTANT_ID,
    name=AssistantName("Resumidor de documentos"),
    system_kind="document_summarizer",
)


class Assistants:
    def __init__(self, *items: Assistant) -> None:
        self.items = list(items)

    def list_all(self) -> list[Assistant]:
        return list(self.items)

    def get_by_id(self, assistant_id: AssistantId) -> Assistant | None:
        return next((item for item in self.items if item.id == assistant_id), None)


class Preferences:
    def __init__(self) -> None:
        self.saved: dict[str, HomeAssistantSelection] = {}

    def get(self, owner_user_id: str) -> HomeAssistantSelection | None:
        return self.saved.get(owner_user_id)

    def replace(self, owner_user_id: str, selection: HomeAssistantSelection) -> None:
        self.saved[owner_user_id] = selection


class SummarizerFixture:
    def __init__(self) -> None:
        self.access = AccessFixture()
        self.conversations = Conversations()
        self.documents = Documents()
        self.summaries = Summaries()
        self.storage = Storage()
        self.vector_store = VectorStore()
        self.queue = InMemoryIngestionJobQueue(self.documents)
        self.clock = ManualClock()
        self.remover = PersonalDocumentRemover(
            documents=self.documents,
            summaries=self.summaries,
            vector_store=self.vector_store,
            file_storage=self.storage,
            access_control=self.access.control,
        )

    def conversation(self, conversation_id: str = "c1", owner: str = "ana", assistant=SUMMARIZER_ASSISTANT_ID):
        return self.conversations.save(
            Conversation(id=ConversationId(conversation_id), assistant_id=assistant, owner_user_id=owner)
        )

    def upload_use_case(self) -> UploadSummaryDocumentUseCase:
        return UploadSummaryDocumentUseCase(
            conversations=self.conversations,
            documents=self.documents,
            summaries=self.summaries,
            document_indexer=Indexer(),
            file_storage=self.storage,
            job_queue=self.queue,
            access_control=self.access.control,
            max_file_bytes=MAX_BYTES,
            clock=self.clock,
        )

    def upload(self, conversation_id: str = "c1", user=ANA, name="contrato-ficticio.docx", content=b"texto"):
        return self.upload_use_case().execute(
            UploadSummaryDocumentInput(
                user=user, conversation_id=conversation_id, source_name=name, raw_content=content
            )
        )

    def reading(self, cls, **extra):
        return cls(
            conversations=self.conversations,
            documents=self.documents,
            summaries=self.summaries,
            access_control=self.access.control,
            **extra,
        )


class UploadTestCase(unittest.TestCase):
    """CT-143: RF-114, RF-115, RN-58, RN-60 e RN-67."""

    def setUp(self) -> None:
        self.fx = SummarizerFixture()
        self.fx.conversation()

    def test_upload_creates_a_pending_personal_document_and_a_job(self) -> None:
        result = self.fx.upload()
        self.assertEqual(result.stage, "enviado")
        document = self.fx.documents.get_personal_by_conversation(ConversationId("c1"))
        assert document is not None
        self.assertEqual(
            (document.owner_user_id, document.assistant_id, document.status),
            ("ana", SUMMARIZER_ASSISTANT_ID, DocumentStatus.PENDING),
        )
        self.assertEqual(document.expires_at - document.created_at, timedelta(days=30))
        self.assertIn(document.storage_key, self.fx.storage.files)
        jobs = list(self.fx.queue.jobs.values())
        self.assertEqual([(job.document_id, job.kind) for job in jobs], [(document.id, IngestionJobKind.INGEST)])
        self.assertIs(self.fx.summaries.get(document.id).stage, SummaryStage.UPLOADED)  # type: ignore[union-attr]

    def test_audit_has_no_content(self) -> None:
        self.fx.upload(content=b"conteudo secreto ficticio")
        event = self.fx.access.audit.events[-1]
        self.assertEqual(event.action, AuditAction.SUMMARY_DOCUMENT_UPLOADED.value)
        self.assertEqual(event.details["format"], ".docx")
        self.assertEqual(len(event.details["content_hash"]), 64)  # SHA-256
        self.assertNotIn("conteudo secreto", str(event.details))

    def test_someone_elses_conversation_is_not_found(self) -> None:
        for user in (BRUNO, admin()):
            with self.subTest(user=user.id), self.assertRaises(ConversationNotFoundError):
                self.fx.upload(user=user)

    def test_only_summarizer_conversations_accept_documents(self) -> None:
        self.fx.conversation("c2", assistant=AssistantId("rh"))
        with self.assertRaises(NotSummarizerConversationError):
            self.fx.upload("c2")

    def test_one_document_per_conversation(self) -> None:
        """D8."""
        self.fx.upload()
        with self.assertRaises(ConversationDocumentExistsError):
            self.fx.upload(name="outro.pdf")

    def test_size_format_and_empty_file(self) -> None:
        with self.assertRaises(DocumentTooLargeError):
            self.fx.upload(content=b"x" * (MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            self.fx.upload(name="planilha.xlsx")
        with self.assertRaises(ValueError):
            self.fx.upload(content=b"")
        self.assertEqual(self.fx.documents.items, {})

    def test_daily_quota_counts_failed_and_expired(self) -> None:
        """RN-60 e D20: 10 por dia, falhas e lapides contam."""
        for index in range(10):
            self.fx.conversation(f"q{index}")
            self.fx.upload(f"q{index}")
        expired = next(iter(self.fx.documents.items.values()))
        self.fx.documents.save(expired.mark_expired())
        self.fx.conversation("q10")
        with self.assertRaises(SummaryDailyLimitError) as caught:
            self.fx.upload("q10")
        self.assertEqual(caught.exception.limit, 10)
        self.fx.clock.advance(timedelta(hours=24, seconds=1).total_seconds())
        self.fx.upload("q10")

    def test_failure_after_saving_rolls_back(self) -> None:
        self.fx.queue.fail_next_enqueue = True
        with self.assertRaises(RuntimeError):
            self.fx.upload()
        self.assertEqual(self.fx.documents.items, {})
        self.assertEqual(self.fx.storage.files, {})


class ReadAndRetryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = SummarizerFixture()
        self.fx.conversation()
        self.fx.upload()
        self.document = self.fx.documents.get_personal_by_conversation(ConversationId("c1"))
        self.ref = SummaryConversationInput(user=ANA, conversation_id="c1")

    def test_status_follows_the_stages(self) -> None:
        status = self.fx.reading(GetSummaryDocumentStatusUseCase)
        self.assertEqual(status.execute(self.ref).stage, "enviado")
        indexed = self.document.start_processing(1).mark_indexed(
            embedding_model="m", pipeline_version="p", chunk_count=3
        )
        self.fx.documents.save(indexed)
        self.fx.summaries.set_stage(self.document.id, SummaryStage.SUMMARIZING, batches_done=2, batches_total=5)
        result = status.execute(self.ref)
        self.assertEqual((result.stage, result.done, result.total, result.questions_available), ("resumindo", 2, 5, True))

    def test_stored_summary_only_when_ready(self) -> None:
        stored = self.fx.reading(GetStoredSummaryUseCase)
        with self.assertRaises(SummaryNotReadyError):
            stored.execute(self.ref)
        self.fx.summaries.complete(
            self.document.id, content="Resumo [1]", citations=(), prompt_version="v1", model="m"
        )
        self.assertEqual(stored.execute(self.ref).content, "Resumo [1]")

    def test_conversation_without_document_and_other_users(self) -> None:
        self.fx.conversation("vazia")
        status = self.fx.reading(GetSummaryDocumentStatusUseCase)
        with self.assertRaises(SummaryDocumentNotFoundError):
            status.execute(SummaryConversationInput(user=ANA, conversation_id="vazia"))
        with self.assertRaises(ConversationNotFoundError):
            status.execute(SummaryConversationInput(user=BRUNO, conversation_id="c1"))

    def test_retry_only_a_failed_summary_without_new_quota(self) -> None:
        """RN-64."""
        retry = self.fx.reading(RetrySummaryUseCase, job_queue=self.fx.queue)
        with self.assertRaises(SummaryNotFailedError):
            retry.execute(self.ref)
        indexed = self.document.start_processing(1).mark_indexed(
            embedding_model="m", pipeline_version="p", chunk_count=3
        )
        self.fx.documents.save(indexed)
        self.fx.summaries.fail(self.document.id, "summary_failed")
        result = retry.execute(self.ref)
        self.assertEqual(result.stage, "resumindo")
        kinds = sorted(job.kind.value for job in self.fx.queue.jobs.values())
        self.assertEqual(kinds, ["ingestao", "resumo"])
        self.assertEqual(len(self.fx.documents.items), 1)


class RemovalTestCase(unittest.TestCase):
    """RF-120, D9 a D11."""

    def setUp(self) -> None:
        self.fx = SummarizerFixture()
        self.fx.conversation()
        self.fx.upload()
        self.document = self.fx.documents.get_personal_by_conversation(ConversationId("c1"))

    def test_deleting_the_conversation_removes_the_document_first(self) -> None:
        DeleteConversationUseCase(
            self.fx.conversations, self.fx.access.control, personal_documents=self.fx.remover
        ).execute(ConversationRefInput(user=ANA, conversation_id="c1"))
        tombstone = self.fx.documents.get_by_id(self.document.id)
        self.assertIs(tombstone.status, DocumentStatus.EXPIRED)  # type: ignore[union-attr]
        self.assertEqual(self.fx.vector_store.deleted, [(SUMMARIZER_COLLECTION.value, self.document.id.value)])
        self.assertEqual(self.fx.storage.files, {})
        self.assertIs(self.fx.summaries.get(self.document.id).stage, SummaryStage.EXPIRED)  # type: ignore[union-attr]
        self.assertEqual(self.fx.conversations.deleted, ["c1"])
        event = self.fx.access.audit.events[-1]
        self.assertEqual(
            (event.action, event.details["reason"]),
            (AuditAction.SUMMARY_DOCUMENT_DELETED.value, "conversation_deleted"),
        )

    def test_purge_removes_only_due_documents_and_survives_failures(self) -> None:
        self.fx.conversation("c2")
        self.fx.upload("c2")
        purge = PurgeExpiredSummaryDocumentsUseCase(
            documents=self.fx.documents, remover=self.fx.remover, clock=self.fx.clock
        )
        self.assertEqual(purge.execute(), 0)
        self.fx.clock.advance(timedelta(days=30, seconds=1).total_seconds())
        self.fx.vector_store.fail_delete = True
        with self.assertLogs("src.application.use_cases.summary_documents", "ERROR"):
            self.assertEqual(purge.execute(), 0)  # fica para a proxima rodada
        self.fx.vector_store.fail_delete = False
        self.assertEqual(purge.execute(), 2)
        self.assertTrue(all(item.status is DocumentStatus.EXPIRED for item in self.fx.documents.items.values()))
        self.assertEqual(self.fx.access.audit.events[-1].details["reason"], "expired")
        self.assertEqual(purge.execute(), 0)

    def test_removal_is_idempotent(self) -> None:
        expired = self.fx.remover.remove(self.document, reason="expired", actor=ANA)
        self.assertIs(self.fx.remover.remove(expired, reason="expired", actor=ANA), expired)
        self.assertEqual(len(self.fx.vector_store.deleted), 1)


class SystemAssistantGuardsTestCase(unittest.TestCase):
    """CT-142 (casos de uso): RN-55 e RN-56."""

    def setUp(self) -> None:
        self.access = AccessFixture()
        self.control = self.access.control

    def test_writes_on_the_summarizer_are_409_for_the_admin(self) -> None:
        with self.assertRaises(SystemAssistantReadonlyError):
            self.control.require_assistant_edit(admin(), SUMMARIZER_ASSISTANT_ID, "x")
        with self.assertRaises(SystemAssistantReadonlyError):
            self.control.require_document_management(admin(), SUMMARIZER_ASSISTANT_ID, "x")
        with self.assertRaises(SystemAssistantReadonlyError):
            self.control.require_mutable(SUMMARIZER_ASSISTANT_ID)

    def test_configuration_reads_stay_open_to_the_admin(self) -> None:
        """D3: o administrador ve e troca o LLM do resumidor."""
        self.control.require_document_management(
            admin(), SUMMARIZER_ASSISTANT_ID, "assistant.llm_viewed", allow_system=True
        )

    def test_common_users_get_403_before_409(self) -> None:
        for user in (ANA, curator("cur", "rh")):
            with self.subTest(user=user.id), self.assertRaises(AccessDeniedError):
                self.control.require_document_management(user, SUMMARIZER_ASSISTANT_ID, "x")

    def test_every_role_uses_the_summarizer(self) -> None:
        for user in (ANA, curator("cur"), admin()):
            with self.subTest(user=user.id):
                self.control.require_assistant_access(user, SUMMARIZER_ASSISTANT_ID, "chat")

    def test_common_assistants_are_unaffected(self) -> None:
        self.access.link_assistant("rh", "rh")
        self.control.require_document_management(admin(), AssistantId("rh"), "x")
        self.control.require_mutable(AssistantId("rh"))

    def test_listing_marks_the_system_assistant_and_inference_skips_it(self) -> None:
        self.access.link_assistant("rh", "rh")
        rh = Assistant(id=AssistantId("rh"), name=AssistantName("RH"))
        use_case = ListAssistantsUseCase(Assistants(rh, SUMMARIZER), self.control)
        user = make_user("ana", groups=("rh",))
        listed = {item.id: item.is_system for item in use_case.execute(user)}
        self.assertEqual(listed, {"rh": False, SUMMARIZER_ASSISTANT_ID.value: True})
        self.assertEqual([item.id for item in use_case.inference_catalog(user)], ["rh"])
        lonely = use_case.execute(make_user("sem-grupo"))
        self.assertEqual([item.id for item in lonely], [SUMMARIZER_ASSISTANT_ID.value])


class HomeAssistantsWithSummarizerTestCase(unittest.TestCase):
    """RN-57 nos casos de uso da SPEC-016."""

    def setUp(self) -> None:
        self.access = AccessFixture()
        self.access.link_assistant("rh", "rh")
        self.access.link_assistant("fin", "rh")
        assistants = Assistants(
            Assistant(id=AssistantId("rh"), name=AssistantName("RH")),
            Assistant(id=AssistantId("fin"), name=AssistantName("Fin")),
            SUMMARIZER,
        )
        self.preferences = Preferences()
        kwargs = {"preferences": self.preferences, "assistants": assistants, "access_control": self.access.control}
        self.get = GetHomeAssistantsUseCase(**kwargs)
        self.set = SetHomeAssistantsUseCase(**kwargs)
        self.user = make_user("ana", groups=("rh",))

    def test_never_customized(self) -> None:
        result = self.get.execute(self.user)
        self.assertEqual(result.assistant_ids, (SUMMARIZER_ASSISTANT_ID.value, "rh", "fin"))
        self.assertEqual(result.default_assistant_id, SUMMARIZER_ASSISTANT_ID.value)
        self.assertEqual(result.pinned_assistant_id, SUMMARIZER_ASSISTANT_ID.value)

    def test_choose_another_default_or_the_summarizer(self) -> None:
        result = self.set.execute(
            SetHomeAssistantsInput(user=self.user, assistant_ids=("fin",), default_assistant_id="fin")
        )
        self.assertEqual((result.assistant_ids, result.default_assistant_id, result.customized),
                         ((SUMMARIZER_ASSISTANT_ID.value, "fin"), "fin", True))
        result = self.set.execute(
            SetHomeAssistantsInput(
                user=self.user, assistant_ids=("fin",), default_assistant_id=SUMMARIZER_ASSISTANT_ID.value
            )
        )
        self.assertEqual(result.default_assistant_id, SUMMARIZER_ASSISTANT_ID.value)

    def test_summarizer_cannot_take_a_slot(self) -> None:
        with self.assertRaises(HomeAssistantsValidationError) as caught:
            self.set.execute(
                SetHomeAssistantsInput(
                    user=self.user,
                    assistant_ids=(SUMMARIZER_ASSISTANT_ID.value, "rh"),
                    default_assistant_id="rh",
                )
            )
        self.assertEqual(caught.exception.code, "home_assistant_pinned")


class SummarizerInfoTestCase(unittest.TestCase):
    def test_info_comes_from_the_constants(self) -> None:
        info = GetSummarizerInfoUseCase(max_file_bytes=MAX_BYTES).execute(ANA)
        self.assertEqual(info.assistant_id, SUMMARIZER_ASSISTANT_ID.value)
        self.assertEqual((info.max_tokens, info.daily_limit, info.retention_days), (40_000, 10, 30))
        self.assertIn("25 MB", info.welcome_markdown)
        self.assertIn(".docx", info.formats)


if __name__ == "__main__":
    unittest.main()
