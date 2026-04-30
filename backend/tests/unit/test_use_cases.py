import unittest

from src.application.use_cases import (
    CreateAssistantInput,
    CreateAssistantUseCase,
    ListAssistantsUseCase,
    RegisterConversationInput,
    RegisterConversationUseCase,
)
from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
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


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self.items: dict[str, Conversation] = {}

    def save(self, conversation: Conversation) -> Conversation:
        self.items[conversation.id.value] = conversation
        return conversation

    def get_by_id(self, conversation_id: ConversationId) -> Conversation | None:
        return self.items.get(conversation_id.value)

    def save_message(self, message):  # pragma: no cover - not used in this stage
        raise NotImplementedError

    def list_messages(self, conversation_id: ConversationId):  # pragma: no cover - not used
        raise NotImplementedError


class UseCasesTestCase(unittest.TestCase):
    def test_create_assistant_use_case_creates_and_returns_dto(self) -> None:
        repo = InMemoryAssistantRepository()
        use_case = CreateAssistantUseCase(repository=repo)

        created = use_case.execute(
            CreateAssistantInput(
                assistant_id="assistant-abc",
                name="Compliance",
                description="Regras internas",
            )
        )

        self.assertEqual(created.id, "assistant-abc")
        self.assertEqual(created.name, "Compliance")
        self.assertEqual(len(repo.list_all()), 1)

    def test_list_assistants_use_case_maps_entities_to_dtos(self) -> None:
        repo = InMemoryAssistantRepository()
        repo.save(Assistant(id=AssistantId("assistant-1"), name=AssistantName("Financeiro")))
        repo.save(Assistant(id=AssistantId("assistant-2"), name=AssistantName("Juridico")))
        use_case = ListAssistantsUseCase(repository=repo)

        items = use_case.execute()

        self.assertEqual(len(items), 2)
        self.assertEqual({item.id for item in items}, {"assistant-1", "assistant-2"})

    def test_register_conversation_use_case_persists_conversation(self) -> None:
        repo = InMemoryConversationRepository()
        use_case = RegisterConversationUseCase(repository=repo)

        result = use_case.execute(
            RegisterConversationInput(
                conversation_id="conv-1",
                assistant_id="assistant-1",
            )
        )

        self.assertEqual(result.conversation.id, "conv-1")
        self.assertEqual(result.conversation.assistant_id, "assistant-1")
        self.assertIsNotNone(repo.get_by_id(ConversationId("conv-1")))


if __name__ == "__main__":
    unittest.main()
