"""SPEC-018: CT-139, roteamento da mensagem na conversa do resumidor (RN-61)."""

from __future__ import annotations

import unittest

from src.domain import (
    SummarizerRoute,
    SummaryProgress,
    SummaryRequestKind,
    SummaryStage,
    classify_summary_request,
    route_summarizer_message,
)


def progress(stage: SummaryStage, *, questions: bool = False) -> SummaryProgress:
    return SummaryProgress(stage=stage, questions_available=questions)


READY = progress(SummaryStage.READY, questions=True)
SUMMARIZING = SummaryProgress(
    stage=SummaryStage.SUMMARIZING, done=3, total=9, questions_available=True
)
INDEXING = progress(SummaryStage.INDEXING)
SUMMARY_FAILED = SummaryProgress(
    stage=SummaryStage.FAILED, failure_code="summary_failed", questions_available=True
)
DOCUMENT_FAILED = SummaryProgress(
    stage=SummaryStage.FAILED, failure_code="document_too_long"
)


class ClassifySummaryRequestTestCase(unittest.TestCase):
    """Vocabulario fechado: termo de resumo + so palavras de ligacao = geral."""

    def test_general_requests(self) -> None:
        for text in (
            "resuma",
            "Resumo",
            "resuma o documento",
            "Resuma o documento, por favor.",
            "me dá um resumo",
            "Faça um resumo geral do arquivo",
            "qual é o resumo?",
            "sintetize o texto",
            "visão geral do documento",
            "quais os principais pontos?",
            "pontos principais",
            "  RESUMO COMPLETO  ",
        ):
            with self.subTest(text=text):
                self.assertIs(classify_summary_request(text), SummaryRequestKind.GENERAL)

    def test_tailored_requests(self) -> None:
        for text in (
            "resuma o capítulo 3",
            "resuma em 5 tópicos",
            "resumo para um diretor",
            "faça um resumo executivo",
            "resuma a cláusula de rescisão",
            "visão geral das obrigações financeiras",
        ):
            with self.subTest(text=text):
                self.assertIs(classify_summary_request(text), SummaryRequestKind.TAILORED)

    def test_not_a_summary_request(self) -> None:
        for text in (
            "qual o prazo de vigência?",
            "quem assina o contrato?",
            "quais arquivos você aceita?",
            "",
            "   ",
            "pontos",  # "principais pontos" so vale como expressao
        ):
            with self.subTest(text=text):
                self.assertIs(classify_summary_request(text), SummaryRequestKind.NONE)


class RouteSummarizerMessageTestCase(unittest.TestCase):
    def test_without_document_always_explains(self) -> None:
        """RN-61 item 1: sem documento, qualquer mensagem recebe a explicacao."""
        for text in ("resuma", "qual o prazo?", "oi"):
            with self.subTest(text=text):
                self.assertIs(
                    route_summarizer_message(text, None), SummarizerRoute.CAPABILITIES
                )

    def test_expired_document_explains(self) -> None:
        expired = progress(SummaryStage.EXPIRED)
        self.assertIs(route_summarizer_message("resuma", expired), SummarizerRoute.CAPABILITIES)
        self.assertIs(
            route_summarizer_message("qual o prazo?", expired), SummarizerRoute.CAPABILITIES
        )

    def test_before_indexing_shows_progress(self) -> None:
        """RN-61 item 2."""
        for stage in (SummaryStage.UPLOADED, SummaryStage.EXTRACTING, SummaryStage.INDEXING):
            for text in ("resuma", "qual o prazo?", "resuma em 3 tópicos"):
                with self.subTest(stage=stage, text=text):
                    self.assertIs(
                        route_summarizer_message(text, progress(stage)),
                        SummarizerRoute.PROGRESS,
                    )

    def test_general_request_uses_stored_summary_when_ready(self) -> None:
        """RN-61 item 3."""
        self.assertIs(route_summarizer_message("resuma", READY), SummarizerRoute.STORED_SUMMARY)
        self.assertIs(route_summarizer_message("resuma", SUMMARIZING), SummarizerRoute.PROGRESS)

    def test_tailored_request_uses_mini_summaries_when_ready(self) -> None:
        """RN-61 item 4 (D33)."""
        text = "resuma em 5 tópicos para um diretor"
        self.assertIs(route_summarizer_message(text, READY), SummarizerRoute.TAILORED_SUMMARY)
        self.assertIs(route_summarizer_message(text, SUMMARIZING), SummarizerRoute.PROGRESS)

    def test_other_messages_are_questions_once_indexed(self) -> None:
        """RN-61 item 5 e D34: perguntas liberadas durante o resumo."""
        for state in (SUMMARIZING, READY, SUMMARY_FAILED):
            with self.subTest(stage=state.stage):
                self.assertIs(
                    route_summarizer_message("qual o prazo de vigência?", state),
                    SummarizerRoute.QUESTION,
                )

    def test_summary_failure_keeps_questions_and_reports_on_summary(self) -> None:
        """RN-64: falha no resumo nao derruba as perguntas."""
        self.assertIs(route_summarizer_message("resuma", SUMMARY_FAILED), SummarizerRoute.PROGRESS)

    def test_document_failure_reports_status(self) -> None:
        for text in ("resuma", "qual o prazo?"):
            with self.subTest(text=text):
                self.assertIs(
                    route_summarizer_message(text, DOCUMENT_FAILED), SummarizerRoute.PROGRESS
                )


if __name__ == "__main__":
    unittest.main()
