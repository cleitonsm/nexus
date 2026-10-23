"""SPEC-006: avaliacao das respostas e curadoria (CT-43, RF-61, RN-33)."""

from __future__ import annotations

import unittest
from datetime import timedelta

from access_doubles import AccessFixture, make_user
from operations_doubles import BASE_NOW, Clock, InMemoryFeedback

from src.application.use_cases import (
    ExportFeedbackInput,
    ExportValidatedFeedbackUseCase,
    ListFeedbackInput,
    ListFeedbackUseCase,
    ReviewFeedbackInput,
    ReviewFeedbackUseCase,
    SubmitFeedbackInput,
    SubmitFeedbackUseCase,
)
from src.application.use_cases.manage_feedback import (
    FeedbackNotFoundError,
    MessageNotFoundError,
)
from src.domain import (
    AccessDeniedError,
    AssistantId,
    AuditAction,
    ChatMessage,
    Citation,
    Conversation,
    ConversationId,
    DocumentId,
    DomainValidationError,
    FeedbackRating,
    FeedbackReview,
    FeedbackStatus,
    InvalidFeedbackStateError,
    MessageFeedback,
    MessageId,
    MessageRole,
    Role,
)

ASSISTANT = "assistant-rh"
GROUP = "rh"
OWNER = make_user("user-1", groups=(GROUP,))
STRANGER = make_user("user-2", groups=(GROUP,))
CURATOR = make_user("curadora", roles=(Role.CURATOR,), groups=(GROUP,), name="curadora.rh")
OTHER_CURATOR = make_user("curador-fin", roles=(Role.CURATOR,), groups=("financeiro",))


class ConversationsWithOneTurn:
    def __init__(self) -> None:
        self.conversation = Conversation(
            id=ConversationId("conv-1"),
            assistant_id=AssistantId(ASSISTANT),
            owner_user_id=OWNER.id,
        )
        self.messages = [
            ChatMessage(
                id=MessageId("m-question"),
                conversation_id=self.conversation.id,
                role=MessageRole.USER,
                content="Quanto duram as ferias?",
                created_at=BASE_NOW,
            ),
            ChatMessage(
                id=MessageId("m-answer"),
                conversation_id=self.conversation.id,
                role=MessageRole.ASSISTANT,
                content="Duram vinte dias [1].",
                created_at=BASE_NOW + timedelta(seconds=1),
                citations=(
                    Citation(
                        number=1,
                        document_id=DocumentId("doc-1"),
                        chunk_id="doc-1:0",
                        source_name="politica.pdf",
                        excerpt="Ferias de trinta dias.",
                        score=0.9,
                    ),
                ),
            ),
        ]

    def get_message(self, message_id: str) -> ChatMessage | None:
        return next((m for m in self.messages if m.id.value == message_id), None)

    def get_by_id(self, conversation_id: ConversationId) -> Conversation | None:
        return self.conversation if conversation_id == self.conversation.id else None

    def list_messages(self, conversation_id: ConversationId) -> list[ChatMessage]:
        return list(self.messages)


class FeedbackTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.access = AccessFixture()
        self.access.link_assistant(ASSISTANT, GROUP)
        self.repository = InMemoryFeedback()
        self.conversations = ConversationsWithOneTurn()
        self.clock = Clock()

    def submit(self, rating: str, comment: str | None = None, user=OWNER, message="m-answer"):
        return SubmitFeedbackUseCase(
            conversation_repository=self.conversations,
            feedback_repository=self.repository,
            access_control=self.access.control,
            clock=self.clock,
        ).execute(
            SubmitFeedbackInput(user=user, message_id=message, rating=rating, comment=comment)
        )

    def review(self, feedback_id: str, decision: str, user=CURATOR, **review):
        return ReviewFeedbackUseCase(
            feedback_repository=self.repository,
            access_control=self.access.control,
            clock=self.clock,
        ).execute(
            ReviewFeedbackInput(
                user=user, feedback_id=feedback_id, decision=decision, **review
            )
        )

    def list_pending(self, user=CURATOR):
        return ListFeedbackUseCase(
            feedback_repository=self.repository,
            access_control=self.access.control,
        ).execute(ListFeedbackInput(user=user))


class SubmitFeedbackTestCase(FeedbackTestCase):
    def test_negative_feedback_reaches_the_curator_with_question_and_answer(self) -> None:
        self.submit("nao_util", "A politica diz trinta dias.")
        (item,) = self.list_pending()
        self.assertEqual(item.rating, "nao_util")
        self.assertEqual(item.status, "pendente")
        self.assertEqual(item.comment, "A politica diz trinta dias.")
        self.assertEqual(item.question, "Quanto duram as ferias?")
        self.assertEqual(item.answer, "Duram vinte dias [1].")
        self.assertEqual(item.cited_documents, ("politica.pdf",))

    def test_useful_feedback_keeps_no_conversation_text(self) -> None:
        self.submit("util")
        (stored,) = self.repository.items.values()
        self.assertIs(stored.status, FeedbackStatus.NOT_APPLICABLE)
        self.assertIsNone(stored.question)
        self.assertIsNone(stored.answer)
        self.assertEqual(self.list_pending(), [])

    def test_last_rating_replaces_the_previous_one(self) -> None:
        first = self.submit("nao_util", "errado")
        self.clock.advance(minutes=1)
        second = self.submit("util")
        self.assertEqual(first.id, second.id)
        self.assertEqual(len(self.repository.items), 1)
        self.assertEqual(self.list_pending(), [])

    def test_other_user_cannot_rate_a_private_conversation(self) -> None:
        with self.assertRaises(MessageNotFoundError):
            self.submit("util", user=STRANGER)

    def test_only_assistant_messages_can_be_rated(self) -> None:
        with self.assertRaises(MessageNotFoundError):
            self.submit("util", message="m-question")

    def test_unknown_rating_and_long_comment_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.submit("talvez")
        with self.assertRaises(DomainValidationError):
            self.submit("nao_util", "x" * 1001)

    def test_submission_is_audited_without_the_comment(self) -> None:
        self.submit("nao_util", "comentario reservado")
        events = [
            e for e in self.access.audit.events if e.action == AuditAction.FEEDBACK_SUBMITTED
        ]
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0].details["has_comment"])
        self.assertNotIn("reservado", str(events[0].details))


class CurationTestCase(FeedbackTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.feedback = self.submit("nao_util", "A politica diz trinta dias.")

    def test_common_user_cannot_list_feedback(self) -> None:
        with self.assertRaises(AccessDeniedError):
            self.list_pending(OWNER)

    def test_curator_of_another_group_sees_nothing(self) -> None:
        self.assertEqual(self.list_pending(OTHER_CURATOR), [])
        with self.assertRaises(FeedbackNotFoundError):
            self.review(self.feedback.id, "descartado", user=OTHER_CURATOR)

    def test_validated_item_is_exported_to_the_reference_set(self) -> None:
        self.review(
            self.feedback.id,
            "validado",
            expected_answer="As ferias duram trinta dias.",
            source_documents=("politica.pdf",),
        )
        (item,) = ExportValidatedFeedbackUseCase(
            feedback_repository=self.repository,
            access_control=self.access.control,
        ).execute(ExportFeedbackInput(user=CURATOR, assistant_id=ASSISTANT))
        self.assertEqual(item.question, "Quanto duram as ferias?")
        self.assertEqual(item.expected_answer, "As ferias duram trinta dias.")
        self.assertEqual(item.source_documents, ("politica.pdf",))
        self.assertEqual(item.validated_by, "curadora.rh")
        self.assertEqual(self.list_pending(), [])

    def test_pending_or_discarded_items_are_not_exported(self) -> None:
        self.review(self.feedback.id, "descartado")
        exported = ExportValidatedFeedbackUseCase(
            feedback_repository=self.repository,
            access_control=self.access.control,
        ).execute(ExportFeedbackInput(user=CURATOR, assistant_id=ASSISTANT))
        self.assertEqual(exported, [])

    def test_validation_requires_answer_and_sources_unless_out_of_scope(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.review(self.feedback.id, "validado", expected_answer="Trinta dias.")
        reviewed = self.review(self.feedback.id, "validado", out_of_scope=True)
        self.assertEqual(reviewed.status, "validado")

    def test_reviewed_feedback_cannot_be_reviewed_or_changed_again(self) -> None:
        self.review(self.feedback.id, "descartado")
        with self.assertRaises(InvalidFeedbackStateError):
            self.review(self.feedback.id, "descartado")
        with self.assertRaises(InvalidFeedbackStateError):
            self.submit("util")

    def test_invalid_decision_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.review(self.feedback.id, "pendente")


class FeedbackEntityTestCase(unittest.TestCase):
    def test_only_validated_feedback_becomes_an_evaluation_item(self) -> None:
        feedback = MessageFeedback.submit(
            id="f-1",
            message_id="m-1",
            conversation_id="c-1",
            assistant_id="a-1",
            user_id="u-1",
            rating=FeedbackRating.NOT_USEFUL,
            comment=None,
            question="Pergunta?",
            answer="Resposta.",
            cited_documents=(),
            now=BASE_NOW,
        )
        with self.assertRaises(InvalidFeedbackStateError):
            feedback.to_evaluation_item()
        validated = feedback.validate(
            FeedbackReview(out_of_scope=True), reviewer="curadora", now=BASE_NOW
        )
        item = validated.to_evaluation_item()
        self.assertTrue(item.out_of_scope)
        self.assertTrue(item.id.startswith("feedback-"))


if __name__ == "__main__":
    unittest.main()
