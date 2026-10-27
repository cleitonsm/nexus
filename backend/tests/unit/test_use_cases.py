import unittest

from access_doubles import AccessFixture, admin, make_user
from src.application.use_cases import (
    CreateAssistantInput,
    CreateAssistantUseCase,
    ListAssistantsUseCase,
    ListConversationsInput,
    ListConversationsUseCase,
    RegisterConversationInput,
    RegisterConversationUseCase,
)
from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    ChatMessage,
    Conversation,
    ConversationId,
)


class InMemoryAssistantRepository:
    def __init__(self) -> None:
        self.items: dict[str, Assistant] = {}

    def save(self, assistant: Assistant) -> Assistant:
        self.items[assistant.id.value] = assistant
        return assistant

    def list_all(self) -> list[Assistant]:
        return list(self.items.values())

    def get_by_id(self, assistant_id: AssistantId) -> Assistant | None:
        return self.items.get(assistant_id.value)

    def delete(self, assistant_id: AssistantId) -> bool:
        return self.items.pop(assistant_id.value, None) is not None


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self.items: dict[str, Conversation] = {}
        self.messages: dict[str, list[ChatMessage]] = {}

    def save(self, conversation: Conversation) -> Conversation:
        self.items[conversation.id.value] = conversation
        self.messages.setdefault(
            conversation.id.value,
            list(conversation.messages),
        )
        return conversation

    def get_by_id(self, conversation_id: ConversationId) -> Conversation | None:
        conversation = self.items.get(conversation_id.value)
        if conversation is None:
            return None
        return Conversation(
            id=conversation.id,
            assistant_id=conversation.assistant_id,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            owner_user_id=conversation.owner_user_id,
            messages=tuple(
                sorted(
                    self.messages.get(conversation_id.value, []),
                    key=lambda item: item.created_at,
                )
            ),
        )

    def list_by_assistant(
        self,
        assistant_id: AssistantId,
        owner_user_id: str,
    ) -> list[Conversation]:
        conversations = [
            self.get_by_id(ConversationId(conversation.id.value))
            for conversation in self.items.values()
            if conversation.assistant_id == assistant_id
            and conversation.owner_user_id == owner_user_id
        ]
        return [
            conversation
            for conversation in conversations
            if conversation is not None
        ]

    def save_message(self, message: ChatMessage) -> ChatMessage:
        conversation = self.items.get(message.conversation_id.value)
        if conversation is None:
            raise ValueError("conversation not found")
        self.messages.setdefault(message.conversation_id.value, []).append(message)
        self.items[message.conversation_id.value] = Conversation(
            id=conversation.id,
            assistant_id=conversation.assistant_id,
            created_at=conversation.created_at,
            updated_at=message.created_at,
            owner_user_id=conversation.owner_user_id,
            messages=tuple(self.messages[message.conversation_id.value]),
        )
        return message

    def list_messages(self, conversation_id: ConversationId) -> list[ChatMessage]:
        return list(self.messages.get(conversation_id.value, []))

    def delete(self, conversation_id: ConversationId) -> bool:
        deleted = self.items.pop(conversation_id.value, None) is not None
        self.messages.pop(conversation_id.value, None)
        return deleted


class UseCasesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.access = AccessFixture()
        self.admin = admin()
        self.member = make_user("user-1", groups=("financeiro",))

    def test_create_assistant_use_case_creates_and_returns_dto(self) -> None:
        repo = InMemoryAssistantRepository()
        use_case = CreateAssistantUseCase(repo, self.access.control)

        created = use_case.execute(
            CreateAssistantInput(
                user=self.admin,
                assistant_id="assistant-abc",
                name="Compliance",
                description="Regras internas",
                initial_prompt="Aja como especialista em compliance.",
            )
        )

        self.assertEqual(created.id, "assistant-abc")
        self.assertEqual(created.name, "Compliance")
        self.assertEqual(created.initial_prompt, "Aja como especialista em compliance.")
        self.assertEqual(len(repo.list_all()), 1)

    def test_list_assistants_use_case_maps_entities_to_dtos(self) -> None:
        repo = InMemoryAssistantRepository()
        repo.save(
            Assistant(
                id=AssistantId("assistant-1"),
                name=AssistantName("Financeiro"),
            )
        )
        repo.save(
            Assistant(
                id=AssistantId("assistant-2"),
                name=AssistantName("Juridico"),
            )
        )
        use_case = ListAssistantsUseCase(repo, self.access.control)

        items = use_case.execute(self.admin)

        self.assertEqual(len(items), 2)
        self.assertEqual(
            {item.id for item in items},
            {"assistant-1", "assistant-2"},
        )

    def test_register_conversation_use_case_persists_conversation(self) -> None:
        repo = InMemoryConversationRepository()
        self.access.link_assistant("assistant-1", "financeiro")
        use_case = RegisterConversationUseCase(repo, self.access.control)

        result = use_case.execute(
            RegisterConversationInput(
                user=self.member,
                conversation_id="conv-1",
                assistant_id="assistant-1",
            )
        )

        self.assertEqual(result.conversation.id, "conv-1")
        self.assertEqual(result.conversation.assistant_id, "assistant-1")
        stored = repo.get_by_id(ConversationId("conv-1"))
        self.assertIsNotNone(stored)
        self.assertEqual(stored.owner_user_id, "user-1")

    def test_list_conversations_use_case_returns_assistant_history(self) -> None:
        repo = InMemoryConversationRepository()
        self.access.link_assistant("assistant-1", "financeiro")
        self.access.link_assistant("assistant-2", "financeiro")
        register_use_case = RegisterConversationUseCase(repo, self.access.control)
        for conversation_id, assistant_id in (
            ("conv-1", "assistant-1"),
            ("conv-2", "assistant-1"),
            ("conv-3", "assistant-2"),
        ):
            register_use_case.execute(
                RegisterConversationInput(
                    user=self.member,
                    conversation_id=conversation_id,
                    assistant_id=assistant_id,
                )
            )

        use_case = ListConversationsUseCase(repo, self.access.control)
        result = use_case.execute(
            ListConversationsInput(user=self.member, assistant_id="assistant-1")
        )

        self.assertEqual(len(result.conversations), 2)
        self.assertEqual(
            {item.id for item in result.conversations},
            {"conv-1", "conv-2"},
        )


if __name__ == "__main__":
    unittest.main()
