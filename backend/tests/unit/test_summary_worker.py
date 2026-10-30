"""SPEC-018: worker do resumidor (CT-144 e CT-145).

Ingestao do documento pessoal (contagem antes de vetorizar, escopo nos
trechos, resumo enfileirado depois da indexacao) e job de resumo hierarquico
(mini-resumos, consolidado com citacoes, mensagem postada, uso separado, nova
tentativa que continua de onde parou e falha que preserva as perguntas).
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from access_doubles import AccessFixture
from chat_doubles import ScriptedLLM
from ingestion_doubles import InMemoryIngestionJobQueue, ManualClock
from summarizer_doubles import Documents, Storage, Summaries

from src.application.services import IngestionSettings
from src.application.use_cases.process_ingestion import (
    ProcessNextIngestionJobUseCase,
    RequeueExpiredIngestionJobsUseCase,
)
from src.application.use_cases.summarize_document import SummarizeDocumentUseCase
from src.domain import (
    SUMMARIZER_ASSISTANT_ID,
    USAGE_OPERATION_DOCUMENT_SUMMARY,
    Assistant,
    AssistantName,
    AuditAction,
    BlockType,
    ChatMessage,
    ConversationId,
    Document,
    DocumentBlock,
    DocumentId,
    DocumentStatus,
    DocumentSummary,
    ExtractedDocument,
    IngestionJob,
    IngestionJobKind,
    IngestionJobStatus,
    SummaryStage,
    TokenUsage,
    VectorChunk,
)
from src.infrastructure.chunking import StructuralSummarySplitter


class Words:
    max_tokens = 128

    def count(self, text: str) -> int:
        return len(text.split())


class FakeIndexer:
    """Extrai '# Titulo' como secao e paragrafos separados por linha em branco."""

    embedding_model = "modelo-local"
    embedding_dimension = 4
    sparse_parameters = None

    def supports(self, *, source_name, content_type) -> bool:
        return True

    def extract(self, *, source_name, content_type, raw_content) -> ExtractedDocument:
        blocks, title = [], ()
        for part in raw_content.decode().split("\n\n"):
            part = part.strip()
            if part.startswith("# "):
                title = (part[2:],)
            elif part:
                blocks.append(DocumentBlock(type=BlockType.PARAGRAPH, text=part, section_path=title, page=1))
        return ExtractedDocument(blocks=tuple(blocks))

    def build_chunks(self, *, assistant_id, document_id, source_name, content_type, raw_content,
                     allowed_groups=frozenset(), active=True, extracted=None,
                     owner_user_id=None, conversation_id=None) -> list[VectorChunk]:
        extracted = extracted or self.extract(source_name=source_name, content_type=None, raw_content=raw_content)
        return [
            VectorChunk(
                id=f"{document_id.value}:{index}", document_id=document_id, assistant_id=assistant_id,
                chunk_index=index, source_name=source_name, content_hash="h", text=block.text,
                vector=[1.0, 0, 0, 0], embedding_model=self.embedding_model, active=active,
                owner_user_id=owner_user_id, conversation_id=conversation_id,
            )
            for index, block in enumerate(extracted.blocks)
        ]


class FakeVectorStore:
    def __init__(self) -> None:
        self.aliases: dict[str, str] = {}
        self.collections: set[str] = set()
        self.points: dict[str, VectorChunk] = {}

    def resolve_alias(self, alias):
        from src.domain import CollectionName

        target = self.aliases.get(alias.value)
        return CollectionName(target) if target else None

    def collection_exists(self, name) -> bool:
        return name.value in self.collections

    def ensure_collection(self, collection_name, vector_size) -> None:
        self.collections.add(collection_name.value)

    def point_alias(self, alias, collection_name) -> None:
        self.aliases[alias.value] = collection_name.value

    def delete_collection(self, collection_name) -> None:
        self.collections.discard(collection_name.value)

    def upsert_chunks(self, collection_name, chunks) -> None:
        self.points.update({chunk.id: chunk for chunk in chunks})

    def delete_by_document(self, collection_name, document_id) -> None:
        self.points = {k: v for k, v in self.points.items() if v.document_id != document_id}

    def set_document_active(self, collection_name, document_id, active) -> None:
        from dataclasses import replace

        for key, chunk in list(self.points.items()):
            if chunk.document_id == document_id:
                self.points[key] = replace(chunk, active=active)


class NoReindex:
    def get_running(self, assistant_id):
        return None


class Messages:
    def __init__(self) -> None:
        self.saved: list[ChatMessage] = []

    def save_message(self, message: ChatMessage) -> ChatMessage:
        self.saved.append(message)
        return message


class Summarizer:
    def get_by_id(self, assistant_id):
        return Assistant(id=SUMMARIZER_ASSISTANT_ID, name=AssistantName("Resumidor"),
                         system_kind="document_summarizer")


@dataclass
class Runtime:
    llm_gateway: object
    usage_model: str = "modelo-ficticio"
    usage_pricing: object = None


class Usage:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record(self, user, **kwargs) -> None:
        self.records.append({"user": user.id, **kwargs})


class FailingLLM(ScriptedLLM):
    """Falha nas chamadas de numero ``fail_on`` (a partir de 1)."""

    def __init__(self, *answers, fail_on=()):
        super().__init__(*answers, usage=TokenUsage(input_tokens=10, output_tokens=5))
        self.fail_on = set(fail_on)
        self.count = 0

    def generate_with_usage(self, **kwargs):
        self.count += 1
        if self.count in self.fail_on:
            raise RuntimeError("llm indisponivel")
        return super().generate_with_usage(**kwargs)


def document_text(sections: int, words_per_section: int) -> bytes:
    parts = []
    for index in range(sections):
        parts.append(f"# Cláusula {index + 1}")
        parts.append(" ".join(["palavra"] * words_per_section))
    return "\n\n".join(parts).encode()


class WorkerScenario:
    def __init__(self, content: bytes, *, llm: ScriptedLLM | None = None) -> None:
        self.clock = ManualClock()
        self.documents = Documents()
        self.summaries = Summaries()
        self.storage = Storage()
        self.vector_store = FakeVectorStore()
        self.queue = InMemoryIngestionJobQueue(self.documents)
        self.access = AccessFixture()
        self.messages = Messages()
        self.usage = Usage()
        self.llm = llm or FailingLLM("mini [1]", "## Visão geral\nResumo final [1].")
        settings = IngestionSettings(retry_delays_seconds=(1, 1))
        self.summarizer = SummarizeDocumentUseCase(
            job_queue=self.queue, summaries=self.summaries, conversations=self.messages,
            assistants=Summarizer(), runtime_resolver=lambda _a: Runtime(self.llm),
            document_indexer=FakeIndexer(), splitter=StructuralSummarySplitter(token_counter=Words()),
            file_storage=self.storage, token_counter=Words(), access_control=self.access.control,
            usage_governance=self.usage, settings=settings, clock=self.clock,
        )
        self.worker = ProcessNextIngestionJobUseCase(
            job_queue=self.queue, document_repository=self.documents, vector_store_gateway=self.vector_store,
            document_indexer=FakeIndexer(), file_storage=self.storage, reindex_job_repository=NoReindex(),
            access_control=self.access.control, settings=settings, clock=self.clock,
            summaries=self.summaries, token_counter=Words(), summarizer=self.summarizer,
        )
        key = self.storage.save(assistant_id=SUMMARIZER_ASSISTANT_ID, document_id=DocumentId("d1"),
                                filename="contrato.txt", content=content)
        self.document = self.documents.save(
            Document(id=DocumentId("d1"), assistant_id=SUMMARIZER_ASSISTANT_ID, source_name="contrato.txt",
                     content_hash="h", status=DocumentStatus.PENDING, storage_key=key,
                     owner_user_id="ana", conversation_id=ConversationId("c1"))
        )
        self.summaries.create(DocumentSummary(document_id=self.document.id))
        self.queue.enqueue(IngestionJob(id="j1", document_id=self.document.id))

    def run(self):
        return self.worker.execute()

    def later(self, seconds: float = 5) -> None:
        self.clock.advance(seconds)

    @property
    def summary(self) -> DocumentSummary:
        return self.summaries.get(self.document.id)  # type: ignore[return-value]


class PersonalIngestionTestCase(unittest.TestCase):
    """CT-144."""

    def test_indexes_with_scope_and_enqueues_the_summary(self) -> None:
        scenario = WorkerScenario(document_text(2, 50))
        scenario.run()
        document = scenario.documents.get_by_id(DocumentId("d1"))
        self.assertIs(document.status, DocumentStatus.INDEXED)
        self.assertEqual(scenario.summary.stage, SummaryStage.SUMMARIZING)
        self.assertEqual(scenario.summary.document_tokens, 100)  # texto dos blocos
        points = list(scenario.vector_store.points.values())
        self.assertTrue(points and all(p.owner_user_id == "ana" and p.conversation_id == "c1" and p.active for p in points))
        self.assertIn("assistant-system-document-summarizer", scenario.vector_store.aliases)
        kinds = [job.kind for job in scenario.queue.pending()]
        self.assertEqual(kinds, [IngestionJobKind.SUMMARIZE])
        self.assertEqual(scenario.llm.calls, [])

    def test_too_long_fails_before_embeddings_without_llm(self) -> None:
        """RN-60 e D15."""
        scenario = WorkerScenario(document_text(1, 40_001))
        scenario.run()
        document = scenario.documents.get_by_id(DocumentId("d1"))
        self.assertIs(document.status, DocumentStatus.FAILED)
        self.assertEqual(document.failure_reason, "O documento tem 40.001 tokens; o limite é 40.000.")
        self.assertEqual((scenario.summary.stage, scenario.summary.failure_code), (SummaryStage.FAILED, "document_too_long"))
        self.assertEqual(scenario.vector_store.points, {})
        self.assertEqual(scenario.queue.pending(), [])

    def test_deleted_while_processing_keeps_the_tombstone(self) -> None:
        scenario = WorkerScenario(document_text(1, 20))
        original = scenario.documents.save
        def expire_on_index(document):
            if document.status is DocumentStatus.INDEXED:
                return original(document)
            saved = original(document)
            if document.status is DocumentStatus.PROCESSING:
                # A conversa foi excluida enquanto o worker vetorizava.
                original(saved.mark_expired())
            return saved
        scenario.documents.save = expire_on_index  # type: ignore[method-assign]
        scenario.run()
        self.assertIs(scenario.documents.get_by_id(DocumentId("d1")).status, DocumentStatus.EXPIRED)
        self.assertEqual(scenario.vector_store.points, {})
        self.assertEqual(scenario.queue.pending(), [])


class SummaryJobTestCase(unittest.TestCase):
    """CT-145."""

    def test_two_levels_message_usage_and_audit(self) -> None:
        scenario = WorkerScenario(document_text(3, 3_000))  # 9 mil tokens: dois lotes
        scenario.run()
        scenario.run()
        self.assertEqual(len(scenario.llm.calls), 3)  # 2 mini-resumos + consolidado
        summary = scenario.summary
        self.assertEqual((summary.stage, summary.batches_done, summary.batches_total), (SummaryStage.READY, 2, 2))
        self.assertEqual(summary.content, "## Visão geral\nResumo final [1].")
        self.assertEqual(summary.prompt_version, "2026-10-30.1")
        citation = summary.citations[0]
        self.assertEqual((citation.chunk_id, citation.section_path), ("d1:section:0", "Cláusula 1 … Cláusula 2"))
        self.assertEqual(scenario.messages.saved[0].content, summary.content)
        self.assertEqual(scenario.usage.records[0]["operation"], USAGE_OPERATION_DOCUMENT_SUMMARY)
        self.assertEqual(scenario.usage.records[0]["user"], "ana")
        event = scenario.access.audit.events[-1]
        self.assertEqual(event.action, AuditAction.SUMMARY_DOCUMENT_SUMMARIZED.value)
        self.assertNotIn("palavra", str(event.details))
        self.assertTrue(all(job.status is IngestionJobStatus.DONE for job in scenario.queue.jobs.values()))

    def test_document_goes_as_data_never_as_instruction(self) -> None:
        """RN-66."""
        scenario = WorkerScenario(document_text(1, 50))
        scenario.run()
        scenario.run()
        self.assertTrue(scenario.llm.system_instructions)
        for instruction in scenario.llm.system_instructions:
            self.assertNotIn("palavra", instruction or "")
        first = scenario.llm.calls[0]["context_chunks"]
        self.assertIn("palavra", " ".join(chunk.text for chunk in first))

    def test_retry_continues_from_the_saved_mini_summaries(self) -> None:
        llm = FailingLLM("mini [1]", "Final [1].", fail_on=(2,))
        scenario = WorkerScenario(document_text(3, 3_000), llm=llm)
        scenario.run()
        scenario.run()  # 1o mini-resumo grava; o 2o falha
        self.assertEqual(len(scenario.summaries.list_sections(scenario.document.id)), 1)
        self.assertEqual(scenario.summary.stage, SummaryStage.SUMMARIZING)
        scenario.later()
        scenario.run()
        self.assertEqual(scenario.summary.stage, SummaryStage.READY)
        self.assertEqual(llm.count, 4)  # sem refazer o primeiro lote

    def test_exhausted_failure_keeps_questions(self) -> None:
        """RN-64."""
        llm = FailingLLM("x", fail_on=range(1, 100))
        scenario = WorkerScenario(document_text(1, 50), llm=llm)
        scenario.run()
        for _ in range(3):
            scenario.run()
            scenario.later()
        self.assertEqual((scenario.summary.stage, scenario.summary.failure_code), (SummaryStage.FAILED, "summary_failed"))
        self.assertIs(scenario.documents.get_by_id(DocumentId("d1")).status, DocumentStatus.INDEXED)
        self.assertEqual(scenario.messages.saved, [])

    def test_expired_summary_job_goes_back_to_the_queue(self) -> None:
        scenario = WorkerScenario(document_text(1, 50))
        scenario.run()
        job = scenario.queue.reserve_next(scenario.clock())  # reservado e abandonado
        scenario.later(601)
        RequeueExpiredIngestionJobsUseCase(
            job_queue=scenario.queue, document_repository=scenario.documents,
            vector_store_gateway=scenario.vector_store, access_control=scenario.access.control,
            clock=scenario.clock, summaries=scenario.summaries,
        ).execute()
        self.assertIs(scenario.queue.jobs[job.id].status, IngestionJobStatus.PENDING)



class TombstoneTestCase(unittest.TestCase):
    """Revisao de 2026-10-30: lapides antigas nao forcam recriar a collection."""

    def test_old_model_tombstone_is_ignored(self) -> None:
        from src.domain import SUMMARIZER_ASSISTANT_ID as SID

        scenario = WorkerScenario(document_text(1, 20))
        old = Document(
            id=DocumentId("velho"), assistant_id=SID, source_name="velho.pdf", content_hash="h",
            status=DocumentStatus.EXPIRED, owner_user_id="ana", embedding_model="modelo-antigo",
        )
        scenario.documents.items["velho"] = old
        scenario.vector_store.aliases["assistant-system-document-summarizer"] = (
            "assistant-system-document-summarizer-v1"
        )
        scenario.vector_store.collections.add("assistant-system-document-summarizer-v1")
        scenario.run()
        self.assertEqual(
            scenario.vector_store.aliases["assistant-system-document-summarizer"],
            "assistant-system-document-summarizer-v1",
        )

if __name__ == "__main__":
    unittest.main()
