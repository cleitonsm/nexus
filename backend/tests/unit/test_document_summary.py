"""SPEC-018: regras puras do resumidor.

CT-140 (lotes de secao e tamanho do resumo, RN-62 e RN-63), CT-146 (texto da
finalidade a partir das constantes, RF-119 e D37) e as entidades novas
(documento pessoal, assistente de sistema, progresso, RN-58 e RN-60).
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from src.domain import (
    DAILY_SUMMARY_DOCUMENTS,
    MAX_SUMMARY_DOCUMENT_TOKENS,
    SUMMARIZER_ASSISTANT_ID,
    SUMMARY_BATCH_MAX_TOKENS,
    SUMMARY_BATCH_MIN_TOKENS,
    SUMMARY_BATCH_TARGET_TOKENS,
    SUMMARY_DOCUMENT_RETENTION,
    Assistant,
    AssistantId,
    AssistantName,
    ConversationId,
    Document,
    DocumentId,
    DocumentStatus,
    DocumentSummary,
    DomainValidationError,
    InvalidDocumentStateError,
    PersonalScope,
    SectionTokens,
    SummarizerCapabilities,
    SummaryProgress,
    SummaryStage,
    capabilities_markdown,
    daily_summary_limit_reached,
    document_too_long_message,
    exceeds_summary_token_limit,
    plan_consolidation_groups,
    plan_summary_batches,
    summary_progress,
    target_summary_words,
)

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)


def section(index: int, *paragraphs: int, title: str = "", page: int | None = None) -> SectionTokens:
    return SectionTokens(
        index=index, title=title or f"Seção {index}", paragraph_tokens=paragraphs, page_start=page
    )


def personal_document(**changes: object) -> Document:
    values: dict[str, object] = {
        "id": DocumentId("doc-1"),
        "assistant_id": SUMMARIZER_ASSISTANT_ID,
        "source_name": "contrato-ficticio.docx",
        "content_hash": "abc",
        "status": DocumentStatus.PENDING,
        "owner_user_id": "usuario.rh",
        "conversation_id": ConversationId("conv-1"),
        "expires_at": NOW + SUMMARY_DOCUMENT_RETENTION,
    }
    values.update(changes)
    return Document(**values)  # type: ignore[arg-type]


class ConstantsTestCase(unittest.TestCase):
    def test_values_chosen_by_the_author(self) -> None:
        self.assertEqual(MAX_SUMMARY_DOCUMENT_TOKENS, 40_000)  # D13
        self.assertEqual(SUMMARY_DOCUMENT_RETENTION, timedelta(days=30))  # D9
        self.assertEqual(DAILY_SUMMARY_DOCUMENTS, 10)  # D20
        self.assertEqual(
            (SUMMARY_BATCH_MIN_TOKENS, SUMMARY_BATCH_TARGET_TOKENS, SUMMARY_BATCH_MAX_TOKENS),
            (4_000, 6_000, 8_000),
        )  # D22


class TokenLimitTestCase(unittest.TestCase):
    """RN-60 e D15."""

    def test_limit_is_inclusive(self) -> None:
        self.assertFalse(exceeds_summary_token_limit(40_000))
        self.assertTrue(exceeds_summary_token_limit(40_001))

    def test_message_shows_count_and_limit_in_pt_br(self) -> None:
        self.assertEqual(
            document_too_long_message(52_000),
            "O documento tem 52.000 tokens; o limite é 40.000.",
        )

    def test_daily_limit(self) -> None:
        self.assertFalse(daily_summary_limit_reached(9))
        self.assertTrue(daily_summary_limit_reached(10))
        self.assertTrue(daily_summary_limit_reached(11))


class SummaryBatchesTestCase(unittest.TestCase):
    """CT-140, RN-63."""

    def test_short_document_is_one_batch(self) -> None:
        batches = plan_summary_batches([section(0, 800), section(1, 1_200)])
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0].tokens, 2_000)
        self.assertEqual([piece.section_index for piece in batches[0].pieces], [0, 1])

    def test_sections_are_grouped_around_the_target(self) -> None:
        sections = [section(i, 2_000) for i in range(9)]  # 18 mil tokens
        batches = plan_summary_batches(sections)
        self.assertEqual([batch.tokens for batch in batches], [6_000, 6_000, 6_000])

    def test_large_section_is_split_by_paragraph(self) -> None:
        batches = plan_summary_batches([section(0, *([1_000] * 12))])  # 12 mil
        self.assertEqual([batch.tokens for batch in batches], [6_000, 6_000])
        first, second = batches
        self.assertEqual(
            (first.pieces[0].paragraph_start, first.pieces[0].paragraph_end), (0, 6)
        )
        self.assertEqual(
            (second.pieces[0].paragraph_start, second.pieces[0].paragraph_end), (6, 12)
        )

    def test_small_last_batch_joins_the_previous(self) -> None:
        sections = [section(0, 3_000), section(1, 3_000), section(2, 1_500)]
        batches = plan_summary_batches(sections)
        self.assertEqual([batch.tokens for batch in batches], [7_500])

    def test_small_last_batch_stays_when_join_passes_max(self) -> None:
        sections = [section(0, 5_000), section(1, 3_500)]
        batches = plan_summary_batches(sections)
        self.assertEqual([batch.tokens for batch in batches], [5_000, 3_500])

    def test_batch_below_minimum_grows_until_target_is_reachable(self) -> None:
        """Um lote abaixo de 4 mil aceita passar do alvo, ate o maximo."""
        batches = plan_summary_batches([section(0, 3_500), section(1, 3_500), section(2, 3_500)])
        self.assertEqual([batch.tokens for batch in batches], [7_000, 3_500])

    def test_no_batch_passes_the_maximum(self) -> None:
        sizes = [700, 7_900, 300, 4_100, 6_000, 2_500, 8_000, 50]
        batches = plan_summary_batches([section(i, size) for i, size in enumerate(sizes)])
        self.assertTrue(all(batch.tokens <= SUMMARY_BATCH_MAX_TOKENS for batch in batches))
        self.assertEqual(sum(batch.tokens for batch in batches), sum(sizes))

    def test_order_is_preserved(self) -> None:
        sections = [section(i, 1_500) for i in range(10)]
        batches = plan_summary_batches(sections)
        order = [piece.section_index for batch in batches for piece in batch.pieces]
        self.assertEqual(order, list(range(10)))

    def test_empty_sections_are_ignored_and_empty_document_is_rejected(self) -> None:
        batches = plan_summary_batches([section(0, 0), section(1, 500)])
        self.assertEqual([piece.section_index for piece in batches[0].pieces], [1])
        with self.assertRaises(DomainValidationError):
            plan_summary_batches([section(0, 0)])
        with self.assertRaises(DomainValidationError):
            plan_summary_batches([])

    def test_paragraph_above_maximum_must_be_split_before(self) -> None:
        with self.assertRaises(DomainValidationError):
            plan_summary_batches([section(0, 8_001)])

    def test_titles_and_pages_travel_with_the_pieces(self) -> None:
        batches = plan_summary_batches([section(0, 500, title="Cláusula 1", page=3)])
        piece = batches[0].pieces[0]
        self.assertEqual((piece.title, piece.page_start), ("Cláusula 1", 3))


class ConsolidationGroupsTestCase(unittest.TestCase):
    """RN-63 e D23: terceiro nivel so acima de 8 mil tokens."""

    def test_single_group_up_to_the_maximum(self) -> None:
        self.assertEqual(plan_consolidation_groups([800] * 10), ((0, 1, 2, 3, 4, 5, 6, 7, 8, 9),))

    def test_groups_when_above_the_maximum(self) -> None:
        groups = plan_consolidation_groups([3_000, 3_000, 3_000, 3_000])
        self.assertEqual(groups, ((0, 1), (2, 3)))


class TargetWordsTestCase(unittest.TestCase):
    """RN-62 e D27: proporcional, entre 300 e 1000 palavras."""

    def test_clamped_proportion(self) -> None:
        cases = ((500, 300), (2_000, 300), (12_000, 300), (20_000, 500), (40_000, 1_000))
        for tokens, words in cases:
            with self.subTest(tokens=tokens):
                self.assertEqual(target_summary_words(tokens), words)

    def test_rejects_negative(self) -> None:
        with self.assertRaises(DomainValidationError):
            target_summary_words(-1)


class CapabilitiesTestCase(unittest.TestCase):
    """CT-146, RF-119 e D37: o texto vem so das constantes."""

    def caps(self, **changes: object) -> SummarizerCapabilities:
        values: dict[str, object] = {
            "formats": (".txt", ".md", ".markdown", ".pdf", ".doc", ".docx"),
            "max_bytes": 25 * 1024 * 1024,
        }
        values.update(changes)
        return SummarizerCapabilities(**values)  # type: ignore[arg-type]

    def test_defaults_come_from_the_domain_constants(self) -> None:
        caps = self.caps()
        self.assertEqual(caps.max_tokens, MAX_SUMMARY_DOCUMENT_TOKENS)
        self.assertEqual(caps.retention_days, 30)
        self.assertEqual(caps.daily_limit, DAILY_SUMMARY_DOCUMENTS)
        self.assertEqual(caps.max_megabytes_label, "25 MB")

    def test_welcome_text_carries_every_limit(self) -> None:
        text = capabilities_markdown(self.caps(), reason="welcome")
        for expected in (
            "Resumidor de documentos",
            ".pdf",
            ".docx",
            ".txt",
            "25 MB",
            "40.000 tokens",
            "55 a 60 páginas",
            "30 dias",
            "10 documentos por dia",
            "OCR",
            "Tabelas com a estrutura preservada",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_text_follows_the_values(self) -> None:
        text = capabilities_markdown(
            self.caps(max_bytes=10 * 1024 * 1024, formats=(".pdf",), daily_limit=3),
            reason="welcome",
        )
        self.assertIn("10 MB", text)
        self.assertIn("3 documentos por dia", text)
        self.assertNotIn(".docx", text)

    def test_reasons_change_only_the_opening(self) -> None:
        welcome = capabilities_markdown(self.caps(), reason="welcome")
        missing = capabilities_markdown(self.caps(), reason="no_document")
        expired = capabilities_markdown(self.caps(), reason="expired")
        self.assertIn("anexe", missing.lower())
        self.assertIn("expirou", expired)
        self.assertNotEqual(welcome.splitlines()[0], missing.splitlines()[0])
        self.assertEqual(welcome.splitlines()[-3:], expired.splitlines()[-3:])

    def test_invalid_capabilities(self) -> None:
        for changes in ({"formats": ()}, {"max_bytes": 0}, {"daily_limit": -1}):
            with self.subTest(changes=changes):
                with self.assertRaises(DomainValidationError):
                    self.caps(**changes)


class PersonalDocumentTestCase(unittest.TestCase):
    """RN-58 e ADR 0014."""

    def test_personal_document(self) -> None:
        document = personal_document()
        self.assertTrue(document.is_personal)
        self.assertEqual(
            document.personal_scope,
            PersonalScope(owner_user_id="usuario.rh", conversation_id=ConversationId("conv-1")),
        )

    def test_base_document_is_not_personal(self) -> None:
        document = Document(
            id=DocumentId("d"), assistant_id=AssistantId("a"), source_name="x", content_hash="h"
        )
        self.assertFalse(document.is_personal)
        self.assertIsNone(document.personal_scope)

    def test_conversation_requires_owner(self) -> None:
        with self.assertRaises(DomainValidationError):
            personal_document(owner_user_id=None)

    def test_tombstone_keeps_owner_without_conversation(self) -> None:
        """T7: lapide depois da exclusao da conversa."""
        document = personal_document(conversation_id=None, status=DocumentStatus.EXPIRED)
        self.assertTrue(document.is_personal)
        self.assertIsNone(document.personal_scope)

    def test_personal_document_expires_from_any_live_state(self) -> None:
        for status in (
            DocumentStatus.PENDING,
            DocumentStatus.PROCESSING,
            DocumentStatus.INDEXED,
            DocumentStatus.FAILED,
        ):
            with self.subTest(status=status):
                expired = personal_document(status=status, chunk_count=3).mark_expired()
                self.assertIs(expired.status, DocumentStatus.EXPIRED)
                self.assertEqual(expired.chunk_count, 0)
                self.assertIsNone(expired.storage_key)

    def test_expired_is_final_and_only_for_personal(self) -> None:
        expired = personal_document().mark_expired()
        with self.assertRaises(InvalidDocumentStateError):
            expired.mark_expired()
        base = Document(
            id=DocumentId("d"), assistant_id=AssistantId("a"), source_name="x", content_hash="h"
        )
        with self.assertRaises(InvalidDocumentStateError):
            base.mark_expired()

    def test_personal_scope_requires_values(self) -> None:
        with self.assertRaises(DomainValidationError):
            PersonalScope(owner_user_id=" ", conversation_id=ConversationId("c"))


class SystemAssistantTestCase(unittest.TestCase):
    def test_system_kind(self) -> None:
        summarizer = Assistant(
            id=SUMMARIZER_ASSISTANT_ID,
            name=AssistantName("Resumidor de documentos"),
            system_kind="document_summarizer",
        )
        common = Assistant(id=AssistantId("a"), name=AssistantName("RH"))
        self.assertTrue(summarizer.is_system)
        self.assertFalse(common.is_system)

    def test_blank_system_kind_is_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            Assistant(id=AssistantId("a"), name=AssistantName("x"), system_kind=" ")


class SummaryProgressTestCase(unittest.TestCase):
    """D36 e RN-64: etapas a partir do documento e do resumo gravado."""

    def summary(self, stage: SummaryStage, **changes: object) -> DocumentSummary:
        values: dict[str, object] = {"document_id": DocumentId("doc-1"), "stage": stage}
        values.update(changes)
        return DocumentSummary(**values)  # type: ignore[arg-type]

    def test_stages_before_indexing(self) -> None:
        document = personal_document(status=DocumentStatus.PENDING)
        uploaded = summary_progress(document, self.summary(SummaryStage.UPLOADED))
        self.assertIs(uploaded.stage, SummaryStage.UPLOADED)
        self.assertFalse(uploaded.questions_available)
        processing = personal_document(status=DocumentStatus.PROCESSING, attempts=1)
        self.assertIs(
            summary_progress(processing, self.summary(SummaryStage.INDEXING)).stage,
            SummaryStage.INDEXING,
        )
        self.assertIs(summary_progress(processing, None).stage, SummaryStage.EXTRACTING)

    def test_summarizing_with_questions_available(self) -> None:
        document = personal_document(status=DocumentStatus.INDEXED)
        result = summary_progress(
            document, self.summary(SummaryStage.SUMMARIZING, batches_done=4, batches_total=9)
        )
        self.assertEqual(
            result,
            SummaryProgress(
                stage=SummaryStage.SUMMARIZING, done=4, total=9, questions_available=True
            ),
        )
        self.assertIs(summary_progress(document, None).stage, SummaryStage.SUMMARIZING)

    def test_ready_and_summary_failure(self) -> None:
        document = personal_document(status=DocumentStatus.INDEXED)
        ready = summary_progress(document, self.summary(SummaryStage.READY, content="Resumo"))
        self.assertIs(ready.stage, SummaryStage.READY)
        failed = summary_progress(
            document, self.summary(SummaryStage.FAILED, failure_code="summary_failed")
        )
        self.assertEqual((failed.stage, failed.failure_code), (SummaryStage.FAILED, "summary_failed"))
        self.assertTrue(failed.questions_available)

    def test_document_failure_and_expiration(self) -> None:
        failed = personal_document(
            status=DocumentStatus.FAILED,
            failure_reason="O documento tem 52.000 tokens; o limite é 40.000.",
        )
        result = summary_progress(
            failed, self.summary(SummaryStage.FAILED, failure_code="document_too_long")
        )
        self.assertEqual(
            (result.stage, result.failure_code, result.questions_available),
            (SummaryStage.FAILED, "document_too_long", False),
        )
        self.assertEqual(result.failure_detail, failed.failure_reason)
        unknown = summary_progress(failed, self.summary(SummaryStage.EXTRACTING))
        self.assertEqual(unknown.failure_code, "processing_failed")
        expired = personal_document(status=DocumentStatus.EXPIRED)
        self.assertIs(summary_progress(expired, None).stage, SummaryStage.EXPIRED)

    def test_progress_validation(self) -> None:
        for changes in ({"done": -1}, {"total": -1}, {"done": 3, "total": 2}):
            with self.subTest(changes=changes):
                with self.assertRaises(DomainValidationError):
                    SummaryProgress(stage=SummaryStage.SUMMARIZING, **changes)  # type: ignore[arg-type]

    def test_ready_summary_requires_content(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.summary(SummaryStage.READY)


class UsageOperationTestCase(unittest.TestCase):
    """RN-65: o uso do resumo e separado das perguntas."""

    def test_default_is_chat_and_unknown_is_rejected(self) -> None:
        from src.domain import USAGE_OPERATION_CHAT, USAGE_OPERATION_DOCUMENT_SUMMARY, UsageRecord

        self.assertEqual(UsageRecord(id="u", user_id="ana", model="m").operation, USAGE_OPERATION_CHAT)
        UsageRecord(id="u", user_id="ana", model="m", operation=USAGE_OPERATION_DOCUMENT_SUMMARY)
        with self.assertRaises(DomainValidationError):
            UsageRecord(id="u", user_id="ana", model="m", operation="outra")


if __name__ == "__main__":
    unittest.main()
