"""PC-D5: conversas anteriores a autenticacao, so para o administrador."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from access_doubles import AccessFixture, admin, curator, make_user

from src.application.use_cases import (
    ArchivedConversationInput,
    ConversationNotFoundError,
    DeleteArchivedConversationUseCase,
    GetArchivedConversationUseCase,
    ListArchivedConversationsUseCase,
)
from src.domain import (
    AccessDeniedError,
    AssistantId,
    ChatMessage,
    Conversation,
    ConversationId,
    MessageId,
    MessageRole,
)

BASE = datetime(2026, 10, 1, tzinfo=UTC)


class InMemoryConversations:
    def __init__(self) -> None:
        self.items: dict[str, Conversation] = {}

    def add(self, conversation_id: str, *, owner: str | None, minutes: int = 0) -> None:
        cid = ConversationId(conversation_id)
        message = ChatMessage(
            id=MessageId(f"{conversation_id}-m1"),
            conversation_id=cid,
            role=MessageRole.USER,
            content="Qual a politica de ferias?",
        )
        self.items[conversation_id] = Conversation(
            id=cid,
            assistant_id=AssistantId("rh"),
            name="Ferias",
            updated_at=BASE + timedelta(minutes=minutes),
            messages=(message,),
            owner_user_id=owner,
        )

    def get_by_id(self, conversation_id: ConversationId) -> Conversation | None:
        return self.items.get(conversation_id.value)

    def list_archived(self) -> list[Conversation]:
        return sorted(
            (item for item in self.items.values() if item.owner_user_id is None),
            key=lambda item: item.updated_at,
            reverse=True,
        )

    def delete(self, conversation_id: ConversationId) -> bool:
        return self.items.pop(conversation_id.value, None) is not None


class ArchivedConversationsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.access = AccessFixture()
        self.repository = InMemoryConversations()
        self.repository.add("antiga-1", owner=None, minutes=1)
        self.repository.add("antiga-2", owner=None, minutes=5)
        self.repository.add("privada", owner="user-1")

    def ref(self, conversation_id: str, user=None) -> ArchivedConversationInput:
        return ArchivedConversationInput(
            user=user or admin(), conversation_id=conversation_id
        )

    def test_admin_lists_only_archived_conversations_most_recent_first(self) -> None:
        items = ListArchivedConversationsUseCase(
            self.repository, self.access.control
        ).execute(admin())
        self.assertEqual([item.id for item in items], ["antiga-2", "antiga-1"])
        self.assertEqual(items[0].message_count, 1)
        event = self.access.audit.last("archived_conversation.consulted")
        self.assertEqual(event.details["count"], 2)

    def test_admin_reads_an_archived_conversation_and_it_is_audited(self) -> None:
        conversation = GetArchivedConversationUseCase(
            self.repository, self.access.control
        ).execute(self.ref("antiga-1"))
        self.assertEqual(conversation.messages[0].content, "Qual a politica de ferias?")
        event = self.access.audit.last("archived_conversation.viewed")
        self.assertEqual(event.resource_id, "antiga-1")

    def test_private_conversation_is_never_exposed_as_archived(self) -> None:
        with self.assertRaises(ConversationNotFoundError):
            GetArchivedConversationUseCase(
                self.repository, self.access.control
            ).execute(self.ref("privada"))
        with self.assertRaises(ConversationNotFoundError):
            DeleteArchivedConversationUseCase(
                self.repository, self.access.control
            ).execute(self.ref("privada"))
        self.assertIn("privada", self.repository.items)

    def test_admin_deletes_an_archived_conversation(self) -> None:
        DeleteArchivedConversationUseCase(
            self.repository, self.access.control
        ).execute(self.ref("antiga-1"))
        self.assertNotIn("antiga-1", self.repository.items)
        event = self.access.audit.last("archived_conversation.deleted")
        self.assertEqual(event.details["message_count"], 1)

    def test_unknown_conversation_is_not_found(self) -> None:
        with self.assertRaises(ConversationNotFoundError):
            GetArchivedConversationUseCase(
                self.repository, self.access.control
            ).execute(self.ref("nao-existe"))

    def test_curator_and_user_are_denied_and_the_denial_is_audited(self) -> None:
        for user in (curator("curadora", "rh"), make_user("user-1", groups=("rh",))):
            with self.subTest(user=user.id):
                with self.assertRaises(AccessDeniedError):
                    ListArchivedConversationsUseCase(
                        self.repository, self.access.control
                    ).execute(user)
                with self.assertRaises(AccessDeniedError):
                    GetArchivedConversationUseCase(
                        self.repository, self.access.control
                    ).execute(self.ref("antiga-1", user))
                with self.assertRaises(AccessDeniedError):
                    DeleteArchivedConversationUseCase(
                        self.repository, self.access.control
                    ).execute(self.ref("antiga-1", user))
        self.assertIn("access.denied", self.access.audit.actions())
        self.assertIn("antiga-1", self.repository.items)


if __name__ == "__main__":
    unittest.main()
