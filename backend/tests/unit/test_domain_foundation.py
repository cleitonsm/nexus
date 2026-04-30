import unittest

from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    ChatMessage,
    CollectionName,
    Conversation,
    ConversationId,
    DomainValidationError,
    MessageId,
    MessageRole,
)


class DomainFoundationTestCase(unittest.TestCase):
    def test_assistant_name_must_not_be_empty(self) -> None:
        with self.assertRaises(DomainValidationError):
            AssistantName(" ")

    def test_collection_name_is_derived_and_normalized(self) -> None:
        collection = CollectionName.from_assistant_id(AssistantId("Assistente Principal"))
        self.assertEqual(collection.value, "assistant-assistente-principal")

    def test_conversation_appends_messages_immutably(self) -> None:
        conversation = Conversation(
            id=ConversationId("conv-1"),
            assistant_id=AssistantId("assistant-1"),
        )

        message = ChatMessage(
            id=MessageId("msg-1"),
            conversation_id=ConversationId("conv-1"),
            role=MessageRole.USER,
            content="Como funciona o Nexus?",
        )
        updated = conversation.append_message(message)

        self.assertEqual(len(conversation.messages), 0)
        self.assertEqual(len(updated.messages), 1)
        self.assertEqual(updated.messages[0].content, "Como funciona o Nexus?")

    def test_message_from_other_conversation_is_rejected(self) -> None:
        conversation = Conversation(
            id=ConversationId("conv-1"),
            assistant_id=AssistantId("assistant-1"),
        )
        invalid_message = ChatMessage(
            id=MessageId("msg-2"),
            conversation_id=ConversationId("conv-2"),
            role=MessageRole.USER,
            content="Pergunta",
        )

        with self.assertRaises(DomainValidationError):
            conversation.append_message(invalid_message)

    def test_assistant_entity_keeps_value_objects(self) -> None:
        assistant = Assistant(id=AssistantId("a-1"), name=AssistantName("Financeiro"))
        self.assertEqual(assistant.id.value, "a-1")
        self.assertEqual(assistant.name.value, "Financeiro")


if __name__ == "__main__":
    unittest.main()
