"""CT-149 (SPEC-018): migracao 0013 e repositorios do resumidor no PostgreSQL.

Mesmo arranjo do CT-49 (``test_migrations``): banco temporario no PostgreSQL do
Compose e Alembic em subprocesso. Sem PostgreSQL, o teste e pulado. Execute
dentro do container do backend.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from test_migrations import SCRIPT, _admin_engine

try:
    import sqlalchemy as sa
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session
except ImportError:  # pragma: no cover
    sa = None

from src.domain import (
    SUMMARIZER_ASSISTANT_ID,
    USAGE_OPERATION_DOCUMENT_SUMMARY,
    AssistantId,
    Citation,
    Conversation,
    ConversationDocumentExistsError,
    ConversationId,
    Document,
    DocumentId,
    DocumentStatus,
    DocumentSummary,
    DocumentSummarySection,
    HomeAssistantSelection,
    SummaryStage,
    TokenUsage,
    UsageLimits,
    UsageQuery,
    UsageRecord,
)

NOW = datetime.now(UTC)


class DocumentSummarizerStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.admin = _admin_engine()
        if self.admin is None:
            self.skipTest("PostgreSQL indisponivel")
        self.name = f"nexus_ct149_{uuid4().hex[:10]}"
        with self.admin.connect() as connection:
            connection.execute(sa.text(f'CREATE DATABASE "{self.name}"'))
        self.addCleanup(self._drop)
        base = make_url(
            os.getenv("DATABASE_URL", "postgresql+psycopg://nexus:nexus@postgres:5432/nexus")
        )
        self.url = base.set(database=self.name)
        self.engine = sa.create_engine(self.url)
        self.addCleanup(self.engine.dispose)

    def _drop(self) -> None:
        self.engine.dispose()
        with self.admin.connect() as connection:
            connection.execute(sa.text(f'DROP DATABASE IF EXISTS "{self.name}" WITH (FORCE)'))
        self.admin.dispose()

    def _alembic(self, action: str, revision: str) -> None:
        env = {**os.environ, "DATABASE_URL": self.url.render_as_string(hide_password=False)}
        result = subprocess.run(
            [sys.executable, "-c", SCRIPT, action, revision],
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, f"{action} {revision}:\n{result.stderr}")

    def _session(self) -> Session:
        self._alembic("upgrade", "head")
        session = Session(self.engine)
        self.addCleanup(session.close)
        return session

    def _conversation(self, session: Session, conversation_id: str, owner: str) -> None:
        from src.infrastructure.database import PostgresConversationRepository

        PostgresConversationRepository(session).save(
            Conversation(
                id=ConversationId(conversation_id),
                assistant_id=SUMMARIZER_ASSISTANT_ID,
                owner_user_id=owner,
            )
        )

    def _personal(self, document_id: str, conversation_id: str | None, owner: str = "ana", **changes):
        values: dict[str, object] = {
            "id": DocumentId(document_id),
            "assistant_id": SUMMARIZER_ASSISTANT_ID,
            "source_name": "contrato-ficticio.docx",
            "content_hash": uuid4().hex,
            "status": DocumentStatus.PENDING,
            "owner_user_id": owner,
            "conversation_id": ConversationId(conversation_id) if conversation_id else None,
            "expires_at": NOW + timedelta(days=30),
        }
        values.update(changes)
        return Document(**values)  # type: ignore[arg-type]

    # --- Migracao ---------------------------------------------------------

    def test_summarizer_is_created_once_and_survives_up_down_up(self) -> None:
        from src.infrastructure.database import PostgresAssistantRepository

        self._alembic("upgrade", "head")
        self._alembic("downgrade", "0012_user_home_assistants")
        self.assertNotIn("document_summaries", sa.inspect(self.engine).get_table_names())
        self._alembic("upgrade", "head")
        with Session(self.engine) as session:
            system = [
                item for item in PostgresAssistantRepository(session).list_all() if item.is_system
            ]
        self.assertEqual([item.id for item in system], [SUMMARIZER_ASSISTANT_ID])
        self.assertEqual(system[0].name.value, "Resumidor de documentos")
        self.assertIsNone(system[0].llm_credential_id)  # segue a padrao
        with self.assertRaises(IntegrityError), self.engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO assistants (id, name, created_at, system_kind) "
                    "VALUES ('outro', 'Outro', now(), 'document_summarizer')"
                )
            )

    def test_old_usage_rows_become_chat(self) -> None:
        self._alembic("upgrade", "0012_user_home_assistants")
        with self.engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO usage_records (id, user_id, model, input_tokens, output_tokens, "
                    "estimated_cost, fallback_used, failed, occurred_at) "
                    "VALUES ('u1', 'ana', 'm', 1, 1, 0, false, false, now())"
                )
            )
        self._alembic("upgrade", "head")
        with self.engine.connect() as connection:
            operation = connection.execute(
                sa.text("SELECT operation FROM usage_records WHERE id = 'u1'")
            ).scalar_one()
        self.assertEqual(operation, "chat")

    def test_database_checks(self) -> None:
        self._session()
        with self.assertRaises(IntegrityError), self.engine.begin() as connection:
            # Conversa sem dono (T7).
            connection.execute(
                sa.text(
                    "INSERT INTO conversations (id, assistant_id, created_at, updated_at) "
                    "VALUES ('c0', :a, now(), now())"
                ),
                {"a": SUMMARIZER_ASSISTANT_ID.value},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO documents (id, assistant_id, source_name, content_hash, "
                    "metadata_json, created_at, conversation_id) "
                    "VALUES ('d0', :a, 'x', 'h', '{}', now(), 'c0')"
                ),
                {"a": SUMMARIZER_ASSISTANT_ID.value},
            )
        with self.assertRaises(IntegrityError), self.engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO usage_records (id, user_id, model, input_tokens, output_tokens, "
                    "estimated_cost, fallback_used, failed, occurred_at, operation) "
                    "VALUES ('u2', 'ana', 'm', 0, 0, 0, false, false, now(), 'outra')"
                )
            )

    # --- Documento pessoal --------------------------------------------------

    def test_personal_document_round_trip_and_one_per_conversation(self) -> None:
        from src.infrastructure.database import PostgresDocumentRepository

        session = self._session()
        self._conversation(session, "c1", "ana")
        documents = PostgresDocumentRepository(session)
        saved = documents.save(self._personal("d1", "c1"))
        self.assertEqual(saved.owner_user_id, "ana")
        self.assertEqual(saved.conversation_id, ConversationId("c1"))
        self.assertEqual(documents.get_personal_by_conversation(ConversationId("c1")), saved)
        self.assertIsNone(documents.get_personal_by_conversation(ConversationId("outra")))
        with self.assertRaises(ConversationDocumentExistsError):
            documents.save(self._personal("d2", "c1"))
        # A sessao continua utilizavel depois do erro (fix-7).
        self.assertIsNotNone(documents.get_by_id(DocumentId("d1")))

    def test_deleting_the_conversation_leaves_a_tombstone_owner(self) -> None:
        from src.infrastructure.database import (
            PostgresConversationRepository,
            PostgresDocumentRepository,
        )

        session = self._session()
        self._conversation(session, "c1", "ana")
        documents = PostgresDocumentRepository(session)
        documents.save(self._personal("d1", "c1").mark_expired())
        PostgresConversationRepository(session).delete(ConversationId("c1"))
        session.expire_all()
        tombstone = documents.get_by_id(DocumentId("d1"))
        assert tombstone is not None
        self.assertEqual(
            (tombstone.status, tombstone.owner_user_id, tombstone.conversation_id),
            (DocumentStatus.EXPIRED, "ana", None),
        )

    def test_daily_quota_counts_tombstones_and_failures(self) -> None:
        from src.infrastructure.database import PostgresDocumentRepository

        session = self._session()
        documents = PostgresDocumentRepository(session)
        for index in range(3):
            self._conversation(session, f"c{index}", "ana")
        documents.save(self._personal("d0", "c0", created_at=NOW - timedelta(hours=1)))
        documents.save(
            self._personal("d1", "c1", created_at=NOW - timedelta(hours=2)).mark_expired()
        )
        documents.save(self._personal("d2", "c2", created_at=NOW - timedelta(hours=30)))
        documents.save(self._personal("db", None, owner="bruno"))
        self.assertEqual(documents.count_personal_since("ana", NOW - timedelta(hours=24)), 2)
        self.assertEqual(documents.count_personal_since("bruno", NOW - timedelta(hours=24)), 1)

    def test_documents_to_expire(self) -> None:
        from src.infrastructure.database import PostgresDocumentRepository

        session = self._session()
        documents = PostgresDocumentRepository(session)
        for index in range(3):
            self._conversation(session, f"c{index}", "ana")
        documents.save(self._personal("old", "c0", expires_at=NOW - timedelta(days=2)))
        documents.save(self._personal("due", "c1", expires_at=NOW - timedelta(minutes=1)))
        documents.save(self._personal("live", "c2"))
        documents.save(
            self._personal("gone", None, expires_at=NOW - timedelta(days=3)).mark_expired()
        )
        # Revisao de 2026-10-30: lapides nao entram na lista dos indexados.
        self.assertEqual(documents.list_personal_indexed(), [])
        due = documents.list_personal_to_expire(NOW, limit=10)
        self.assertEqual([item.id.value for item in due], ["old", "due"])
        self.assertEqual(len(documents.list_personal_to_expire(NOW, limit=1)), 1)

    # --- Resumo -------------------------------------------------------------

    def test_summary_lifecycle(self) -> None:
        from src.infrastructure.database import (
            PostgresDocumentRepository,
            PostgresDocumentSummaryRepository,
        )

        session = self._session()
        self._conversation(session, "c1", "ana")
        PostgresDocumentRepository(session).save(self._personal("d1", "c1"))
        summaries = PostgresDocumentSummaryRepository(session)
        document_id = DocumentId("d1")
        summaries.create(DocumentSummary(document_id=document_id))
        summaries.set_stage(document_id, SummaryStage.INDEXING)
        summaries.set_stage(
            document_id, SummaryStage.SUMMARIZING, batches_done=1, batches_total=3,
            document_tokens=15_000,
        )
        current = summaries.get(document_id)
        assert current is not None
        self.assertEqual(
            (current.stage, current.batches_done, current.batches_total, current.document_tokens),
            (SummaryStage.SUMMARIZING, 1, 3, 15_000),
        )
        for position in (1, 0):
            summaries.save_section(
                DocumentSummarySection(
                    document_id=document_id, position=position, title=f"Parte {position}",
                    input_tokens=5_000, content="rascunho", page_start=position + 1,
                )
            )
        # Nova tentativa substitui a mesma posicao.
        summaries.save_section(
            DocumentSummarySection(
                document_id=document_id, position=0, title="Parte 0", input_tokens=5_000,
                content="mini-resumo", page_start=1,
            )
        )
        sections = summaries.list_sections(document_id)
        self.assertEqual([(s.position, s.content) for s in sections], [(0, "mini-resumo"), (1, "rascunho")])
        summaries.fail(document_id, "summary_failed")
        self.assertEqual(summaries.get(document_id).failure_code, "summary_failed")  # type: ignore[union-attr]
        citation = Citation(
            number=1, document_id=document_id, chunk_id="d1:section:0",
            source_name="contrato-ficticio.docx", excerpt="mini-resumo",
            section_path="Parte 0", page=1,
        )
        summaries.complete(
            document_id, content="Resumo [1]", citations=(citation,),
            prompt_version="2026-10-30", model="modelo-ficticio",
        )
        ready = summaries.get(document_id)
        assert ready is not None
        self.assertEqual((ready.stage, ready.content, ready.failure_code), (SummaryStage.READY, "Resumo [1]", None))
        self.assertEqual(ready.citations, (citation,))
        summaries.delete_content(document_id)
        expired = summaries.get(document_id)
        assert expired is not None
        self.assertEqual((expired.stage, expired.content, expired.citations), (SummaryStage.EXPIRED, None, ()))
        self.assertEqual(summaries.list_sections(document_id), [])

    # --- Uso (RN-65) ----------------------------------------------------------

    def test_summary_usage_counts_in_cost_but_not_in_limits(self) -> None:
        from src.infrastructure.database import PostgresUsageLimiter, PostgresUsageRecordRepository

        session = self._session()
        records = PostgresUsageRecordRepository(session)
        for index in range(3):
            records.append(
                UsageRecord(
                    id=f"s{index}", user_id="ana", model="m", usage=TokenUsage(100, 10),
                    estimated_cost=Decimal("0.010000"),
                    operation=USAGE_OPERATION_DOCUMENT_SUMMARY,
                )
            )
        records.append(
            UsageRecord(id="q1", user_id="ana", model="m", estimated_cost=Decimal("0.001000"))
        )
        decision = PostgresUsageLimiter(session).check(
            "ana", UsageLimits(per_minute=1, per_day=500), NOW + timedelta(seconds=1)
        )
        self.assertFalse(decision.allowed)  # so a pergunta conta: 1 de 1 no minuto
        decision = PostgresUsageLimiter(session).check(
            "ana", UsageLimits(per_minute=2, per_day=500), NOW + timedelta(seconds=1)
        )
        self.assertTrue(decision.allowed)
        summary = records.summarize_by_user(
            UsageQuery(occurred_from=NOW - timedelta(hours=1), occurred_to=NOW + timedelta(hours=1))
        )[0]
        self.assertEqual(summary.questions, 1)
        self.assertEqual(summary.estimated_cost, Decimal("0.031000"))

    # --- Acesso rapido (RN-57) --------------------------------------------------

    def test_summarizer_as_chosen_default_round_trip(self) -> None:
        from src.domain import Assistant, AssistantName
        from src.infrastructure.database import (
            PostgresAssistantRepository,
            PostgresHomeAssistantPreferenceRepository,
        )

        session = self._session()
        PostgresAssistantRepository(session).save(
            Assistant(id=AssistantId("a"), name=AssistantName("A"))
        )
        preferences = PostgresHomeAssistantPreferenceRepository(session)
        selection = HomeAssistantSelection(
            assistant_ids=(AssistantId("a"),),
            default_id=SUMMARIZER_ASSISTANT_ID,
            pinned_id=SUMMARIZER_ASSISTANT_ID,
        )
        preferences.replace("ana", selection)
        self.assertEqual(preferences.get("ana"), selection)


if __name__ == "__main__":
    unittest.main()
