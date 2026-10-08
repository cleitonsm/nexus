"""SPEC-20261007-004: politica de acesso, permissoes e auditoria.

CT-24 e CT-25 (politica), e, com dubles, os contratos que os testes de
integracao CT-27 a CT-31 conferem contra o ambiente real.
"""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from access_doubles import AccessFixture, admin, curator, make_user
from chat_doubles import (
    ScriptedLLM,
    ScriptedVectorStore,
    WordTokenCounter,
    build_retriever,
    hit,
)
from ingestion_doubles import (
    InMemoryIngestionJobQueue,
    current_documents,
    find_current_by_hash,
)
from src.application.services import (
    AuditTrail,
    DocumentIndexer,
    GroundedAnswerGenerator,
)
from src.application.use_cases import (
    AddMessageInput,
    AddMessageUseCase,
    AssistantNotFoundError,
    ChatWithAssistantInput,
    ChatWithAssistantUseCase,
    ConversationNotFoundError,
    ConversationRefInput,
    CreateAssistantInput,
    CreateAssistantUseCase,
    DeleteAssistantInput,
    DeleteAssistantUseCase,
    DeleteConversationUseCase,
    DescribeCurrentUserUseCase,
    DocumentNotFoundError,
    GetConversationUseCase,
    GetGlobalApiKeyStatusUseCase,
    GetIndexStatusInput,
    GetIndexStatusUseCase,
    IngestDocumentInput,
    IngestDocumentUseCase,
    ProcessNextIngestionJobUseCase,
    ListAssistantsUseCase,
    ListAuditEventsInput,
    ListAuditEventsUseCase,
    ListConversationsInput,
    ListConversationsUseCase,
    ListDocumentsInput,
    ListDocumentsUseCase,
    MAINTENANCE_USER,
    PurgeAuditEventsInput,
    PurgeAuditEventsUseCase,
    RegisterConversationInput,
    RegisterConversationUseCase,
    RunReindexInput,
    RunReindexUseCase,
    SaveGlobalApiKeyInput,
    SaveGlobalApiKeyUseCase,
    SetAssistantGroupsInput,
    SetAssistantGroupsUseCase,
    SetDocumentGroupsInput,
    SetDocumentGroupsUseCase,
    StartReindexInput,
    StartReindexUseCase,
)
from src.domain import (
    AccessDeniedError,
    AccessPolicy,
    Assistant,
    AssistantId,
    AssistantName,
    AuditAction,
    AuditEvent,
    AuditQuery,
    AuthenticatedUser,
    ChatMessage,
    CollectionName,
    Conversation,
    ConversationId,
    Document,
    DocumentId,
    DomainValidationError,
    ReindexInProgressError,
    ReindexJob,
    Role,
    VectorChunk,
)
from src.infrastructure.chunking import StructuralDocumentChunker
from src.infrastructure.documents import SupportedDocumentExtractor
from src.infrastructure.embeddings import Bm25SparseEmbeddingGateway

RH = frozenset({"rh"})
NO_GROUPS: frozenset[str] = frozenset()
ASSISTANT = "assistant-rh"


class AuthenticatedUserTestCase(unittest.TestCase):
    def test_group_paths_and_plain_names_are_the_same_group(self) -> None:
        user = make_user(groups=("/rh", " financeiro "))
        self.assertEqual(user.groups, frozenset({"rh", "financeiro"}))

    def test_name_falls_back_to_the_identifier(self) -> None:
        self.assertEqual(AuthenticatedUser(id=" u1 ").name, "u1")

    def test_empty_identifier_is_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            AuthenticatedUser(id="  ")

    def test_empty_group_name_is_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            make_user(groups=("/",))

    def test_unknown_role_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AuthenticatedUser(id="u1", roles=frozenset({"root"}))  # type: ignore[arg-type]


class AssistantAccessPolicyTestCase(unittest.TestCase):
    """CT-24 (RN-22): negacao por padrao."""

    def test_assistant_without_group_is_denied_to_a_common_user(self) -> None:
        user = make_user(groups=("rh",))
        self.assertFalse(AccessPolicy.can_access_assistant(user, NO_GROUPS))

    def test_assistant_without_group_is_denied_to_a_curator(self) -> None:
        self.assertFalse(
            AccessPolicy.can_access_assistant(curator("c1", "rh"), NO_GROUPS)
        )

    def test_assistant_without_group_is_visible_to_the_administrator(self) -> None:
        self.assertTrue(AccessPolicy.can_access_assistant(admin(), NO_GROUPS))

    def test_user_of_a_linked_group_has_access(self) -> None:
        self.assertTrue(AccessPolicy.can_access_assistant(make_user(groups=("rh",)), RH))

    def test_user_of_another_group_is_denied(self) -> None:
        user = make_user(groups=("financeiro",))
        self.assertFalse(AccessPolicy.can_access_assistant(user, RH))

    def test_user_without_group_is_denied(self) -> None:
        self.assertFalse(AccessPolicy.can_access_assistant(make_user(), RH))

    def test_token_without_a_nexus_role_is_denied_even_in_the_group(self) -> None:
        user = make_user(roles=(), groups=("rh",))
        self.assertFalse(AccessPolicy.can_access_assistant(user, RH))


class RolePolicyTestCase(unittest.TestCase):
    """RN-21: responsabilidades de cada papel."""

    def test_only_the_administrator_manages_assistants_llm_and_audit(self) -> None:
        for user, expected in (
            (admin(), True),
            (curator("c1", "rh"), False),
            (make_user(groups=("rh",)), False),
        ):
            with self.subTest(user=user.id):
                self.assertEqual(AccessPolicy.can_manage_assistants(user), expected)
                self.assertEqual(AccessPolicy.can_configure_llm(user), expected)
                self.assertEqual(AccessPolicy.can_view_audit(user), expected)

    def test_curator_manages_documents_only_where_it_has_access(self) -> None:
        self.assertTrue(AccessPolicy.can_manage_documents(curator("c1", "rh"), RH))
        self.assertFalse(
            AccessPolicy.can_manage_documents(curator("c1", "financeiro"), RH)
        )
        self.assertFalse(AccessPolicy.can_manage_documents(curator("c1", "rh"), NO_GROUPS))

    def test_common_user_does_not_manage_documents(self) -> None:
        self.assertFalse(
            AccessPolicy.can_manage_documents(make_user(groups=("rh",)), RH)
        )

    def test_administrator_manages_documents_of_any_assistant(self) -> None:
        self.assertTrue(AccessPolicy.can_manage_documents(admin(), NO_GROUPS))


class DocumentRestrictionPolicyTestCase(unittest.TestCase):
    """CT-25 (RN-23): a restricao de documento so restringe."""

    BOARD = frozenset({"diretoria"})

    def test_unrestricted_document_follows_the_assistant(self) -> None:
        user = make_user(groups=("rh",))
        self.assertTrue(AccessPolicy.can_read_document(user, RH, NO_GROUPS))

    def test_restricted_document_is_denied_outside_its_groups(self) -> None:
        user = make_user(groups=("rh",))
        self.assertFalse(AccessPolicy.can_read_document(user, RH, self.BOARD))

    def test_restricted_document_is_read_by_its_groups(self) -> None:
        user = make_user(groups=("rh", "diretoria"))
        self.assertTrue(AccessPolicy.can_read_document(user, RH, self.BOARD))

    def test_document_group_does_not_widen_the_assistant_access(self) -> None:
        user = make_user(groups=("diretoria",))
        self.assertFalse(AccessPolicy.can_read_document(user, RH, self.BOARD))

    def test_document_group_does_not_open_an_assistant_without_group(self) -> None:
        user = make_user(groups=("diretoria",))
        self.assertFalse(AccessPolicy.can_read_document(user, NO_GROUPS, self.BOARD))

    def test_restriction_also_applies_to_the_administrator(self) -> None:
        self.assertFalse(AccessPolicy.can_read_document(admin(), RH, self.BOARD))

    def test_filter_rule_matches_empty_restriction_or_common_group(self) -> None:
        match = AccessPolicy.document_matches_groups
        self.assertTrue(match(NO_GROUPS, NO_GROUPS))
        self.assertTrue(match(frozenset({"diretoria", "rh"}), self.BOARD))
        self.assertFalse(match(RH, self.BOARD))
        self.assertFalse(match(NO_GROUPS, self.BOARD))


class ConversationPrivacyPolicyTestCase(unittest.TestCase):
    """RN-24."""

    def test_only_the_owner_reads_the_conversation(self) -> None:
        self.assertTrue(AccessPolicy.owns_conversation(make_user("a"), "a"))
        self.assertFalse(AccessPolicy.owns_conversation(make_user("b"), "a"))

    def test_administrator_does_not_read_conversations_of_others(self) -> None:
        self.assertFalse(AccessPolicy.owns_conversation(admin(), "a"))

    def test_conversation_without_owner_belongs_to_nobody(self) -> None:
        self.assertFalse(AccessPolicy.owns_conversation(admin(), None))
        self.assertFalse(AccessPolicy.owns_conversation(make_user("a"), None))


# --- dubles dos casos de uso -------------------------------------------------


class AssistantRepository:
    def __init__(self, *assistant_ids: str) -> None:
        self.items = {
            item: Assistant(id=AssistantId(item), name=AssistantName(item.upper()))
            for item in assistant_ids
        }

    def save(self, assistant: Assistant) -> Assistant:
        self.items[assistant.id.value] = assistant
        return assistant

    def list_all(self) -> list[Assistant]:
        return list(self.items.values())

    def get_by_id(self, assistant_id: AssistantId) -> Assistant | None:
        return self.items.get(assistant_id.value)

    def delete(self, assistant_id: AssistantId) -> bool:
        return self.items.pop(assistant_id.value, None) is not None


class ConversationRepository:
    def __init__(self) -> None:
        self.items: dict[str, Conversation] = {}
        self.messages: list[ChatMessage] = []

    def save(self, conversation: Conversation) -> Conversation:
        self.items[conversation.id.value] = conversation
        return conversation

    def get_by_id(self, conversation_id: ConversationId) -> Conversation | None:
        return self.items.get(conversation_id.value)

    def list_by_assistant(
        self,
        assistant_id: AssistantId,
        owner_user_id: str,
    ) -> list[Conversation]:
        return [
            item
            for item in self.items.values()
            if item.assistant_id == assistant_id
            and item.owner_user_id == owner_user_id
        ]

    def save_message(self, message: ChatMessage) -> ChatMessage:
        self.messages.append(message)
        return message

    def list_messages(self, conversation_id: ConversationId) -> list[ChatMessage]:
        return [m for m in self.messages if m.conversation_id == conversation_id]

    def delete(self, conversation_id: ConversationId) -> bool:
        return self.items.pop(conversation_id.value, None) is not None

    def add(self, conversation_id: str, owner: str | None) -> None:
        self.save(
            Conversation(
                id=ConversationId(conversation_id),
                assistant_id=AssistantId(ASSISTANT),
                owner_user_id=owner,
            )
        )


class DocumentRepository:
    def __init__(self) -> None:
        self.items: dict[str, Document] = {}

    def save(self, document: Document) -> Document:
        self.items[document.id.value] = document
        return document

    def get_by_id(self, document_id: DocumentId) -> Document | None:
        return self.items.get(document_id.value)

    def list_by_assistant(self, assistant_id: AssistantId) -> list[Document]:
        return current_documents(self.items, assistant_id)

    def find_by_hash(
        self,
        assistant_id: AssistantId,
        content_hash: str,
    ) -> Document | None:
        return find_current_by_hash(self.items, assistant_id, content_hash)

    def delete(self, document_id: DocumentId) -> bool:
        return self.items.pop(document_id.value, None) is not None

    def add(self, document_id: str, storage_key: str | None = None) -> Document:
        return self.save(
            Document(
                id=DocumentId(document_id),
                assistant_id=AssistantId(ASSISTANT),
                source_name=f"{document_id}.md",
                content_hash="hash",
                storage_key=storage_key,
            )
        )


class JobRepository:
    def __init__(self) -> None:
        self.items: dict[str, ReindexJob] = {}

    def save(self, job: ReindexJob) -> ReindexJob:
        self.items[job.id] = job
        return job

    def get_by_id(self, job_id: str) -> ReindexJob | None:
        return self.items.get(job_id)

    def get_latest(self, assistant_id: AssistantId) -> ReindexJob | None:
        return None

    def get_running(self, assistant_id: AssistantId) -> ReindexJob | None:
        for job in self.items.values():
            if job.assistant_id == assistant_id and job.is_running:
                return job
        return None

    def list_running(self) -> list[ReindexJob]:
        return [job for job in self.items.values() if job.is_running]


class GroupVectorStore:
    """Guarda os trechos e registra as regravacoes de restricao."""

    def __init__(self) -> None:
        self.collections: dict[str, list[VectorChunk]] = {}
        self.aliases: dict[str, str] = {}
        self.group_updates: list[tuple[str, str, frozenset[str]]] = []
        self.deleted: list[str] = []
        self.fail_group_update = False

    def ensure_collection(self, collection_name: CollectionName, vector_size: int) -> None:
        self.collections.setdefault(collection_name.value, [])

    def upsert_chunks(self, collection_name: CollectionName, chunks: list[VectorChunk]) -> None:
        physical = self.aliases.get(collection_name.value, collection_name.value)
        self.collections[physical].extend(chunks)

    def set_document_groups(
        self,
        collection_name: CollectionName,
        document_id: DocumentId,
        groups: frozenset[str],
    ) -> None:
        if self.fail_group_update:
            raise RuntimeError("vector store unavailable")
        self.group_updates.append((collection_name.value, document_id.value, groups))

    def delete_by_document(
        self,
        collection_name: CollectionName,
        document_id: DocumentId,
    ) -> None:
        physical = self.aliases.get(collection_name.value, collection_name.value)
        if physical in self.collections:
            self.collections[physical] = [
                chunk
                for chunk in self.collections[physical]
                if chunk.document_id != document_id
            ]

    def set_document_active(
        self,
        collection_name: CollectionName,
        document_id: DocumentId,
        active: bool,
    ) -> None:
        physical = self.aliases.get(collection_name.value, collection_name.value)
        self.collections[physical] = [
            replace(chunk, active=active) if chunk.document_id == document_id else chunk
            for chunk in self.collections.get(physical, [])
        ]

    def delete_collection(self, collection_name: CollectionName) -> None:
        self.deleted.append(collection_name.value)
        self.collections.pop(collection_name.value, None)

    def collection_exists(self, collection_name: CollectionName) -> bool:
        return collection_name.value in self.collections

    def count_points(self, collection_name: CollectionName) -> int:
        physical = self.aliases.get(collection_name.value, collection_name.value)
        return len(self.collections[physical])

    def resolve_alias(self, alias: CollectionName) -> CollectionName | None:
        target = self.aliases.get(alias.value)
        return CollectionName(target) if target else None

    def point_alias(self, alias: CollectionName, collection_name: CollectionName) -> None:
        self.aliases[alias.value] = collection_name.value


class FileStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def save(self, *, assistant_id, document_id, filename, content) -> str:
        key = f"{assistant_id.value}/{document_id.value}"
        self.files[key] = content
        return key

    def load(self, storage_key: str) -> bytes:
        return self.files[storage_key]

    def delete(self, storage_key: str) -> None:
        self.files.pop(storage_key, None)


class OneVectorEmbedding:
    model_name = "modelo-teste"
    dimension = 1

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0]


def _indexer() -> DocumentIndexer:
    return DocumentIndexer(
        extractor=SupportedDocumentExtractor(),
        chunker=StructuralDocumentChunker(
            token_counter=WordTokenCounter(),
            max_tokens=24,
            overlap_sentences=1,
            max_prefix_tokens=8,
        ),
        embedding_gateway=OneVectorEmbedding(),
        sparse_embedding_gateway=Bm25SparseEmbeddingGateway(),
    )


class SecretRepository:
    def __init__(self) -> None:
        self.items: dict[str, str] = {}

    def set_encrypted_value(self, *, key_name: str, encrypted_value: str) -> None:
        self.items[key_name] = encrypted_value

    def get_encrypted_value(self, *, key_name: str) -> str | None:
        return self.items.get(key_name)


class Cipher:
    def encrypt(self, plaintext: str) -> str:
        return f"enc::{plaintext}"

    def decrypt(self, ciphertext: str) -> str:
        return ciphertext.removeprefix("enc::")


class AccessTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.access = AccessFixture()
        self.access.link_assistant(ASSISTANT, "rh")
        self.assistants = AssistantRepository(ASSISTANT, "assistant-sem-grupo")
        self.conversations = ConversationRepository()
        self.documents = DocumentRepository()
        self.jobs = JobRepository()
        self.vector_store = GroupVectorStore()
        self.admin = admin()
        self.rh_user = make_user("ana", groups=("rh",))
        self.finance_user = make_user("bruno", groups=("financeiro",))
        self.rh_curator = curator("carla", "rh")

    def assertDenied(self, user: AuthenticatedUser, attempted: str) -> None:
        event = self.access.audit.last(AuditAction.ACCESS_DENIED)
        self.assertEqual(event.user_id, user.id)
        self.assertEqual(event.details["attempted_action"], attempted)


class AssistantVisibilityTestCase(AccessTestCase):
    """RF-42, RN-22."""

    def _visible_to(self, user: AuthenticatedUser) -> set[str]:
        use_case = ListAssistantsUseCase(self.assistants, self.access.control)
        return {item.id for item in use_case.execute(user)}

    def test_user_sees_only_the_assistants_of_its_groups(self) -> None:
        self.assertEqual(self._visible_to(self.rh_user), {ASSISTANT})

    def test_user_of_another_group_does_not_see_the_assistant(self) -> None:
        self.assertEqual(self._visible_to(self.finance_user), set())

    def test_assistant_without_group_appears_only_to_the_administrator(self) -> None:
        self.assertEqual(
            self._visible_to(self.admin), {ASSISTANT, "assistant-sem-grupo"}
        )

    def test_groups_are_shown_only_to_who_manages_the_assistant(self) -> None:
        use_case = ListAssistantsUseCase(self.assistants, self.access.control)
        self.assertEqual(use_case.execute(self.rh_user)[0].groups, ())
        self.assertEqual(use_case.execute(self.rh_curator)[0].groups, ("rh",))


class AssistantManagementTestCase(AccessTestCase):
    """RN-21: assistentes e permissoes sao do administrador."""

    def test_non_administrator_cannot_create_an_assistant(self) -> None:
        use_case = CreateAssistantUseCase(self.assistants, self.access.control)
        with self.assertRaises(AccessDeniedError):
            use_case.execute(CreateAssistantInput(user=self.rh_curator, name="Novo"))
        self.assertEqual(len(self.assistants.items), 2)
        self.assertDenied(self.rh_curator, "assistant.created")

    def test_created_assistant_has_no_group_and_is_audited(self) -> None:
        use_case = CreateAssistantUseCase(self.assistants, self.access.control)
        created = use_case.execute(
            CreateAssistantInput(user=self.admin, name="Juridico", assistant_id="jur")
        )
        self.assertEqual(created.groups, ())
        self.assertEqual(
            self.access.permissions.get_assistant_groups(AssistantId("jur")),
            frozenset(),
        )
        event = self.access.audit.last(AuditAction.ASSISTANT_CREATED)
        self.assertEqual(event.resource_id, "jur")
        self.assertEqual(event.user_id, self.admin.id)

    def _delete(self, user: AuthenticatedUser, assistant_id: str = ASSISTANT) -> None:
        DeleteAssistantUseCase(
            assistant_repository=self.assistants,
            vector_store_gateway=self.vector_store,
            access_control=self.access.control,
        ).execute(DeleteAssistantInput(user=user, assistant_id=assistant_id))

    def test_administrator_deletes_assistant_and_its_collection(self) -> None:
        self.vector_store.aliases[f"assistant-{ASSISTANT}"] = f"assistant-{ASSISTANT}-v2"
        self._delete(self.admin)
        self.assertNotIn(ASSISTANT, self.assistants.items)
        self.assertEqual(self.vector_store.deleted, [f"assistant-{ASSISTANT}-v2"])
        self.assertIn(AuditAction.ASSISTANT_DELETED, self.access.audit.actions())

    def test_non_administrator_cannot_delete_an_assistant(self) -> None:
        with self.assertRaises(AccessDeniedError):
            self._delete(self.rh_curator)
        self.assertIn(ASSISTANT, self.assistants.items)
        self.assertEqual(self.vector_store.deleted, [])

    def test_deleting_an_unknown_assistant_is_reported(self) -> None:
        with self.assertRaises(AssistantNotFoundError):
            self._delete(self.admin, "nao-existe")

    def _set_groups(self, user: AuthenticatedUser, *groups: str, assistant_id: str = ASSISTANT):
        return SetAssistantGroupsUseCase(
            assistant_repository=self.assistants,
            access_control=self.access.control,
        ).execute(
            SetAssistantGroupsInput(user=user, assistant_id=assistant_id, groups=groups)
        )

    def test_administrator_replaces_the_groups_of_an_assistant(self) -> None:
        result = self._set_groups(self.admin, "/financeiro", "rh", "rh")
        self.assertEqual(result, ("financeiro", "rh"))
        self.assertEqual(
            self.access.permissions.get_assistant_groups(AssistantId(ASSISTANT)),
            frozenset({"financeiro", "rh"}),
        )
        event = self.access.audit.last(AuditAction.ASSISTANT_GROUPS_CHANGED)
        self.assertEqual(event.details["before"], ["rh"])
        self.assertEqual(event.details["after"], ["financeiro", "rh"])

    def test_empty_list_returns_the_assistant_to_administrators_only(self) -> None:
        self.assertEqual(self._set_groups(self.admin), ())
        visible = ListAssistantsUseCase(self.assistants, self.access.control).execute(
            self.rh_user
        )
        self.assertEqual(visible, [])

    def test_non_administrator_cannot_change_groups(self) -> None:
        with self.assertRaises(AccessDeniedError):
            self._set_groups(self.rh_curator, "financeiro")
        self.assertEqual(
            self.access.permissions.get_assistant_groups(AssistantId(ASSISTANT)), RH
        )

    def test_blank_group_name_is_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self._set_groups(self.admin, "rh", "  ")

    def test_unknown_assistant_is_reported(self) -> None:
        with self.assertRaises(AssistantNotFoundError):
            self._set_groups(self.admin, "rh", assistant_id="nao-existe")


class ConversationPrivacyTestCase(AccessTestCase):
    """RF-44, RN-24 (contrato do CT-29)."""

    def setUp(self) -> None:
        super().setUp()
        self.conversations.add("conv-ana", self.rh_user.id)
        self.conversations.add("conv-antiga", None)

    def _ref(self, user: AuthenticatedUser, conversation_id: str) -> ConversationRefInput:
        return ConversationRefInput(user=user, conversation_id=conversation_id)

    def test_new_conversation_belongs_to_who_created_it(self) -> None:
        result = RegisterConversationUseCase(
            self.conversations, self.access.control
        ).execute(
            RegisterConversationInput(
                user=self.rh_user, assistant_id=ASSISTANT, conversation_id="nova"
            )
        )
        stored = self.conversations.get_by_id(ConversationId(result.conversation.id))
        self.assertEqual(stored.owner_user_id, self.rh_user.id)

    def test_conversation_cannot_be_created_on_an_assistant_of_another_group(self) -> None:
        with self.assertRaises(AccessDeniedError):
            RegisterConversationUseCase(
                self.conversations, self.access.control
            ).execute(
                RegisterConversationInput(user=self.finance_user, assistant_id=ASSISTANT)
            )
        self.assertDenied(self.finance_user, "conversation.create")

    def test_owner_reads_its_conversation(self) -> None:
        use_case = GetConversationUseCase(self.conversations, self.access.control)
        self.assertEqual(
            use_case.execute(self._ref(self.rh_user, "conv-ana")).id.value, "conv-ana"
        )

    def test_conversation_of_another_user_is_reported_as_not_found(self) -> None:
        use_case = GetConversationUseCase(self.conversations, self.access.control)
        other_member = make_user("davi", groups=("rh",))
        for user in (other_member, self.admin):
            with self.subTest(user=user.id), self.assertRaises(ConversationNotFoundError):
                use_case.execute(self._ref(user, "conv-ana"))

    def test_conversation_from_before_authentication_is_shown_to_nobody(self) -> None:
        use_case = GetConversationUseCase(self.conversations, self.access.control)
        for user in (self.rh_user, self.admin):
            with self.subTest(user=user.id), self.assertRaises(ConversationNotFoundError):
                use_case.execute(self._ref(user, "conv-antiga"))

    def test_listing_returns_only_the_conversations_of_the_user(self) -> None:
        self.conversations.add("conv-davi", "davi")
        result = ListConversationsUseCase(
            self.conversations, self.access.control
        ).execute(ListConversationsInput(user=self.rh_user, assistant_id=ASSISTANT))
        self.assertEqual([item.id for item in result.conversations], ["conv-ana"])

    def test_listing_requires_access_to_the_assistant(self) -> None:
        with self.assertRaises(AccessDeniedError):
            ListConversationsUseCase(self.conversations, self.access.control).execute(
                ListConversationsInput(user=self.finance_user, assistant_id=ASSISTANT)
            )

    def test_only_the_owner_deletes_the_conversation(self) -> None:
        use_case = DeleteConversationUseCase(self.conversations, self.access.control)
        with self.assertRaises(ConversationNotFoundError):
            use_case.execute(self._ref(self.admin, "conv-ana"))
        self.assertIn("conv-ana", self.conversations.items)
        use_case.execute(self._ref(self.rh_user, "conv-ana"))
        self.assertNotIn("conv-ana", self.conversations.items)

    def test_only_the_owner_adds_messages(self) -> None:
        use_case = AddMessageUseCase(self.conversations, self.access.control)
        with self.assertRaises(ConversationNotFoundError):
            use_case.execute(
                AddMessageInput(
                    user=self.admin,
                    conversation_id="conv-ana",
                    role="user",
                    content="Oi",
                )
            )
        self.assertEqual(self.conversations.messages, [])
        saved = use_case.execute(
            AddMessageInput(
                user=self.rh_user,
                conversation_id="conv-ana",
                role="user",
                content="Oi",
            )
        )
        self.assertEqual(saved.content, "Oi")


class FailingLLM:
    def generate(self, *, prompt, context_chunks, conversation_history) -> str:
        raise RuntimeError("LLM provider is unreachable.")


class ChatAccessTestCase(AccessTestCase):
    """Contratos do CT-27 e do CT-28, com o vector store dublado."""

    def setUp(self) -> None:
        super().setUp()
        self.conversations.add("conv-ana", self.rh_user.id)
        self.store = ScriptedVectorStore(
            [[hit("doc-1", "Trecho confidencial da politica.", source_name="politica.md")]]
        )
        self.llm = ScriptedLLM("Resposta [1].")
        self.use_case = ChatWithAssistantUseCase(
            assistant_repository=self.assistants,
            conversation_repository=self.conversations,
            context_retriever=build_retriever(self.store),
            answer_generator=GroundedAnswerGenerator(llm_gateway=self.llm),
            token_counter=WordTokenCounter(),
            access_control=self.access.control,
        )

    def _ask(self, user: AuthenticatedUser, conversation_id: str = "conv-ana"):
        return self.use_case.execute(
            ChatWithAssistantInput(
                user=user,
                conversation_id=conversation_id,
                question="Qual e a politica de ferias?",
            )
        )

    def test_search_carries_the_groups_of_who_asks(self) -> None:
        self._ask(self.rh_user)
        (call,) = self.store.calls
        self.assertEqual(call["user_groups"], frozenset({"rh"}))
        self.assertEqual(call["collection"], f"assistant-{ASSISTANT}")

    def test_user_that_lost_access_to_the_assistant_is_denied(self) -> None:
        self.access.link_assistant(ASSISTANT, "diretoria")
        with self.assertRaises(AccessDeniedError):
            self._ask(self.rh_user)
        self.assertEqual(self.store.calls, [])
        self.assertEqual(self.llm.calls, [])
        self.assertEqual(self.conversations.messages, [])
        self.assertDenied(self.rh_user, "chat.question")
        denial = self.access.audit.last(AuditAction.ACCESS_DENIED)
        self.assertEqual(denial.details["assistant_id"], ASSISTANT)

    def test_conversation_of_another_user_is_not_found_before_any_search(self) -> None:
        with self.assertRaises(ConversationNotFoundError):
            self._ask(make_user("davi", groups=("rh",)))
        self.assertEqual(self.store.calls, [])
        self.assertEqual(self.conversations.messages, [])

    def test_question_is_audited_with_documents_and_without_any_text(self) -> None:
        self._ask(self.rh_user)
        event = self.access.audit.last(AuditAction.CHAT_QUESTION)
        self.assertEqual(event.user_id, self.rh_user.id)
        self.assertEqual(event.resource_id, ASSISTANT)
        self.assertEqual(event.details["conversation_id"], "conv-ana")
        self.assertFalse(event.details["fallback_used"])
        self.assertEqual(
            event.details["retrieved_documents"],
            [
                {
                    "document_id": "doc-1",
                    "source_name": "politica.md",
                    "chunk_id": "doc-1:0",
                    "score": 0.9,
                }
            ],
        )
        self.assertEqual(event.details["cited_documents"], ["doc-1"])
        serialized = repr(event.details)
        self.assertNotIn("Trecho confidencial", serialized)
        self.assertNotIn("politica de ferias", serialized)
        self.assertNotIn("Resposta", serialized)

    def test_question_without_context_is_audited_as_fallback(self) -> None:
        self.store = ScriptedVectorStore([[]])
        self.use_case = ChatWithAssistantUseCase(
            assistant_repository=self.assistants,
            conversation_repository=self.conversations,
            context_retriever=build_retriever(self.store),
            answer_generator=GroundedAnswerGenerator(llm_gateway=self.llm),
            token_counter=WordTokenCounter(),
            access_control=self.access.control,
        )
        result = self._ask(self.rh_user)
        self.assertTrue(result.fallback_used)
        event = self.access.audit.last(AuditAction.CHAT_QUESTION)
        self.assertTrue(event.details["fallback_used"])
        self.assertEqual(event.details["retrieved_documents"], [])

    def test_failed_question_is_audited_with_the_retrieved_documents(self) -> None:
        self.use_case = ChatWithAssistantUseCase(
            assistant_repository=self.assistants,
            conversation_repository=self.conversations,
            context_retriever=build_retriever(self.store),
            answer_generator=GroundedAnswerGenerator(llm_gateway=FailingLLM()),
            token_counter=WordTokenCounter(),
            access_control=self.access.control,
        )
        with self.assertRaises(RuntimeError):
            self._ask(self.rh_user)
        event = self.access.audit.last(AuditAction.CHAT_QUESTION)
        self.assertTrue(event.details["failed"])
        self.assertEqual(event.details["error_type"], "RuntimeError")
        self.assertEqual(event.details["conversation_id"], "conv-ana")
        self.assertEqual(
            [item["document_id"] for item in event.details["retrieved_documents"]],
            ["doc-1"],
        )
        self.assertNotIn("Trecho confidencial", repr(event.details))

    def test_answered_question_is_marked_as_not_failed(self) -> None:
        self._ask(self.rh_user)
        event = self.access.audit.last(AuditAction.CHAT_QUESTION)
        self.assertFalse(event.details["failed"])


class DocumentManagementTestCase(AccessTestCase):
    """RN-21 e RF-43."""

    CONTENT = b"# Politica\n\nTodo colaborador tem direito a ferias.\n"

    def setUp(self) -> None:
        super().setUp()
        self.storage = FileStorage()

    def _ingest(
        self,
        user: AuthenticatedUser,
        document_id: str = "doc-1",
        groups: tuple[str, ...] = (),
    ):
        """Envio seguido do processamento pelo worker."""
        queue = InMemoryIngestionJobQueue(self.documents, self.jobs)
        indexer = _indexer()
        result = IngestDocumentUseCase(
            document_repository=self.documents,
            vector_store_gateway=self.vector_store,
            document_indexer=indexer,
            file_storage=self.storage,
            job_queue=queue,
            max_file_bytes=1024,
            access_control=self.access.control,
        ).execute(
            IngestDocumentInput(
                user=user,
                assistant_id=ASSISTANT,
                document_id=document_id,
                source_name="politica.md",
                raw_content=self.CONTENT + document_id.encode(),
                groups=groups,
            )
        )
        ProcessNextIngestionJobUseCase(
            job_queue=queue,
            document_repository=self.documents,
            vector_store_gateway=self.vector_store,
            document_indexer=indexer,
            file_storage=self.storage,
            reindex_job_repository=self.jobs,
            access_control=self.access.control,
        ).execute()
        return result

    def _restrict(self, user: AuthenticatedUser, *groups: str, document_id: str = "doc-1"):
        return SetDocumentGroupsUseCase(
            document_repository=self.documents,
            vector_store_gateway=self.vector_store,
            reindex_job_repository=self.jobs,
            access_control=self.access.control,
        ).execute(
            SetDocumentGroupsInput(user=user, document_id=document_id, groups=groups)
        )

    def _stored_groups(self, document_id: str = "doc-1") -> frozenset[str]:
        return self.access.permissions.get_document_groups(DocumentId(document_id))

    def test_curator_with_access_uploads_and_the_upload_is_audited(self) -> None:
        self._ingest(self.rh_curator)
        event = self.access.audit.last(AuditAction.DOCUMENT_UPLOADED)
        self.assertEqual(event.user_id, self.rh_curator.id)
        self.assertEqual(event.details["assistant_id"], ASSISTANT)
        self.assertEqual(event.details["source_name"], "politica.md")
        self.assertNotIn("ferias", repr(event.details))

    def test_uploaded_chunks_start_without_restriction(self) -> None:
        self._ingest(self.admin)
        chunks = self.vector_store.collections[f"assistant-{ASSISTANT}-v1"]
        self.assertTrue(chunks)
        self.assertTrue(all(chunk.allowed_groups == () for chunk in chunks))

    def test_upload_with_groups_writes_restricted_chunks_from_the_start(self) -> None:
        """D8: o documento nunca fica visivel a todo o assistente."""
        result = self._ingest(self.rh_curator, groups=("/diretoria", "rh"))
        chunks = self.vector_store.collections[f"assistant-{ASSISTANT}-v1"]
        self.assertTrue(chunks)
        self.assertTrue(
            all(chunk.allowed_groups == ("diretoria", "rh") for chunk in chunks)
        )
        self.assertEqual(self._stored_groups(), frozenset({"diretoria", "rh"}))
        self.assertEqual(result.groups, ("diretoria", "rh"))
        event = self.access.audit.last(AuditAction.DOCUMENT_UPLOADED)
        self.assertEqual(event.details["groups"], ["diretoria", "rh"])

    def test_upload_with_a_blank_group_is_rejected_before_any_write(self) -> None:
        with self.assertRaises(DomainValidationError):
            self._ingest(self.admin, groups=("rh", "  "))
        self.assertEqual(self.documents.items, {})
        self.assertEqual(self.storage.files, {})
        self.assertEqual(self.vector_store.collections, {})

    def test_common_user_and_foreign_curator_cannot_upload(self) -> None:
        for user in (self.rh_user, curator("eva", "financeiro")):
            with self.subTest(user=user.id), self.assertRaises(AccessDeniedError):
                self._ingest(user)
        self.assertEqual(self.documents.items, {})
        self.assertEqual(self.storage.files, {})
        self.assertEqual(self.vector_store.collections, {})

    def test_restriction_is_stored_written_to_the_index_and_audited(self) -> None:
        self.documents.add("doc-1")
        result = self._restrict(self.rh_curator, "/diretoria", "rh")
        self.assertEqual(result.groups, ("diretoria", "rh"))
        self.assertEqual(self._stored_groups(), frozenset({"diretoria", "rh"}))
        self.assertEqual(
            self.vector_store.group_updates,
            [(f"assistant-{ASSISTANT}", "doc-1", frozenset({"diretoria", "rh"}))],
        )
        event = self.access.audit.last(AuditAction.DOCUMENT_GROUPS_CHANGED)
        self.assertEqual(event.resource_id, "doc-1")
        self.assertEqual(event.details["before"], [])
        self.assertEqual(event.details["after"], ["diretoria", "rh"])

    def test_empty_list_removes_the_restriction(self) -> None:
        self.documents.add("doc-1")
        self.access.restrict_document("doc-1", "diretoria")
        self.assertEqual(self._restrict(self.admin).groups, ())
        self.assertEqual(self._stored_groups(), frozenset())
        self.assertEqual(self.vector_store.group_updates[-1][2], frozenset())

    def test_user_without_document_management_cannot_restrict(self) -> None:
        self.documents.add("doc-1")
        for user in (self.rh_user, curator("eva", "financeiro")):
            with self.subTest(user=user.id), self.assertRaises(AccessDeniedError):
                self._restrict(user, "diretoria")
        self.assertEqual(self._stored_groups(), frozenset())
        self.assertEqual(self.vector_store.group_updates, [])

    def test_index_failure_restores_the_previous_restriction(self) -> None:
        self.documents.add("doc-1")
        self.access.restrict_document("doc-1", "diretoria")
        self.vector_store.fail_group_update = True
        with self.assertRaises(RuntimeError):
            self._restrict(self.admin)
        self.assertEqual(self._stored_groups(), frozenset({"diretoria"}))
        self.assertNotIn(
            AuditAction.DOCUMENT_GROUPS_CHANGED, self.access.audit.actions()
        )

    def test_restriction_is_refused_during_a_reindex(self) -> None:
        self.documents.add("doc-1")
        self.jobs.save(
            ReindexJob(
                id="job-1",
                assistant_id=AssistantId(ASSISTANT),
                target_collection=f"assistant-{ASSISTANT}-v2",
            )
        )
        with self.assertRaises(ReindexInProgressError):
            self._restrict(self.admin, "diretoria")
        self.assertEqual(self._stored_groups(), frozenset())

    def test_unknown_document_is_reported(self) -> None:
        with self.assertRaises(DocumentNotFoundError):
            self._restrict(self.admin, "diretoria", document_id="nao-existe")

    def test_reindex_writes_the_current_restriction_into_the_new_chunks(self) -> None:
        self._ingest(self.admin, "doc-1")
        self._ingest(self.admin, "doc-2")
        self.access.restrict_document("doc-1", "rh", "diretoria")
        self.access.permissions.document_assistant.update(
            {"doc-1": ASSISTANT, "doc-2": ASSISTANT}
        )
        job = StartReindexUseCase(
            document_repository=self.documents,
            vector_store_gateway=self.vector_store,
            reindex_job_repository=self.jobs,
            access_control=self.access.control,
        ).execute(StartReindexInput(user=self.rh_curator, assistant_id=ASSISTANT))
        finished = RunReindexUseCase(
            document_repository=self.documents,
            vector_store_gateway=self.vector_store,
            document_indexer=_indexer(),
            file_storage=self.storage,
            reindex_job_repository=self.jobs,
            permission_repository=self.access.permissions,
        ).execute(RunReindexInput(job_id=job.id))
        self.assertEqual(finished.status, "succeeded")
        chunks = self.vector_store.collections[f"assistant-{ASSISTANT}-v2"]
        by_document = {
            document_id: {
                chunk.allowed_groups
                for chunk in chunks
                if chunk.document_id.value == document_id
            }
            for document_id in ("doc-1", "doc-2")
        }
        self.assertEqual(by_document["doc-1"], {("diretoria", "rh")})
        self.assertEqual(by_document["doc-2"], {()})
        self.assertIn(
            AuditAction.ASSISTANT_REINDEX_STARTED, self.access.audit.actions()
        )

    def test_reindex_and_index_status_require_document_management(self) -> None:
        with self.assertRaises(AccessDeniedError):
            StartReindexUseCase(
                document_repository=self.documents,
                vector_store_gateway=self.vector_store,
                reindex_job_repository=self.jobs,
                access_control=self.access.control,
            ).execute(StartReindexInput(user=self.rh_user, assistant_id=ASSISTANT))
        self.assertEqual(self.jobs.items, {})
        with self.assertRaises(AccessDeniedError):
            GetIndexStatusUseCase(
                document_repository=self.documents,
                vector_store_gateway=self.vector_store,
                embedding_gateway=OneVectorEmbedding(),
                reindex_job_repository=self.jobs,
                access_control=self.access.control,
            ).execute(GetIndexStatusInput(user=self.rh_user, assistant_id=ASSISTANT))

    def test_listing_shows_each_document_with_its_restriction(self) -> None:
        self.documents.add("doc-1")
        self.documents.add("doc-2")
        self.access.restrict_document("doc-1", "diretoria")
        use_case = ListDocumentsUseCase(
            document_repository=self.documents,
            access_control=self.access.control,
        )
        listed = use_case.execute(
            ListDocumentsInput(user=self.rh_curator, assistant_id=ASSISTANT)
        )
        self.assertEqual(
            {item.id: item.groups for item in listed},
            {"doc-1": ("diretoria",), "doc-2": ()},
        )
        with self.assertRaises(AccessDeniedError):
            use_case.execute(
                ListDocumentsInput(user=self.rh_user, assistant_id=ASSISTANT)
            )


class LlmConfigurationTestCase(AccessTestCase):
    """RF-47 (contrato do CT-30)."""

    def setUp(self) -> None:
        super().setUp()
        self.secrets = SecretRepository()

    def test_non_administrator_cannot_save_or_read_the_status(self) -> None:
        save = SaveGlobalApiKeyUseCase(
            secret_repository=self.secrets,
            secret_cipher=Cipher(),
            access_control=self.access.control,
        )
        status = GetGlobalApiKeyStatusUseCase(
            secret_repository=self.secrets,
            access_control=self.access.control,
        )
        for user in (self.rh_curator, self.rh_user):
            with self.subTest(user=user.id):
                with self.assertRaises(AccessDeniedError):
                    save.execute(SaveGlobalApiKeyInput(user=user, api_key="sk-x"))
                with self.assertRaises(AccessDeniedError):
                    status.execute(user)
        self.assertEqual(self.secrets.items, {})

    def test_key_change_is_audited_without_the_key(self) -> None:
        SaveGlobalApiKeyUseCase(
            secret_repository=self.secrets,
            secret_cipher=Cipher(),
            access_control=self.access.control,
        ).execute(SaveGlobalApiKeyInput(user=self.admin, api_key="sk-segredo-123"))
        event = self.access.audit.last(AuditAction.LLM_API_KEY_CHANGED)
        self.assertEqual(event.user_id, self.admin.id)
        self.assertNotIn("sk-segredo-123", repr(event))


class AuditTrailTestCase(AccessTestCase):
    """RF-45, RN-25 (contrato do CT-31)."""

    def _list(self, user: AuthenticatedUser, **filters: object):
        return ListAuditEventsUseCase(
            audit_log_repository=self.access.audit,
            access_control=self.access.control,
        ).execute(ListAuditEventsInput(user=user, **filters))

    def test_session_start_is_audited_with_roles_and_groups(self) -> None:
        described = DescribeCurrentUserUseCase(self.access.control).execute(
            self.rh_curator
        )
        self.assertEqual(described.roles, (Role.CURATOR.value,))
        self.assertEqual(described.groups, ("rh",))
        event = self.access.audit.last(AuditAction.SESSION_STARTED)
        self.assertEqual(event.user_id, self.rh_curator.id)
        self.assertEqual(event.details["user_name"], self.rh_curator.name)

    def test_only_the_administrator_consults_the_trail(self) -> None:
        with self.assertRaises(AccessDeniedError):
            self._list(self.rh_curator)
        self.assertDenied(self.rh_curator, "audit.consulted")

    def test_consultation_is_itself_audited_but_not_returned(self) -> None:
        DescribeCurrentUserUseCase(self.access.control).execute(self.rh_user)
        events = self._list(self.admin)
        self.assertEqual([event.action for event in events], ["auth.session_started"])
        self.assertEqual(
            self.access.audit.actions(),
            ["auth.session_started", "audit.consulted"],
        )

    def test_trail_is_filtered_by_user_action_assistant_and_period(self) -> None:
        clock = iter(
            datetime(2026, 10, day, 12, 0, tzinfo=UTC) for day in (1, 2, 3)
        )
        trail = AuditTrail(self.access.audit, clock=lambda: next(clock))
        from src.domain import AuditResource

        trail.record(
            self.rh_user,
            AuditAction.CHAT_QUESTION,
            resource_type=AuditResource.ASSISTANT,
            resource_id=ASSISTANT,
            details={"assistant_id": ASSISTANT},
        )
        trail.record(
            self.finance_user,
            AuditAction.CHAT_QUESTION,
            resource_type=AuditResource.ASSISTANT,
            resource_id="outro",
            details={"assistant_id": "outro"},
        )
        trail.record(
            self.rh_user,
            AuditAction.SESSION_STARTED,
            resource_type=AuditResource.SESSION,
        )

        def ids(**filters: object) -> list[str]:
            return [event.user_id for event in self._list(self.admin, **filters)]

        self.assertEqual(ids(user_id="ana", action="chat.question"), ["ana"])
        self.assertEqual(ids(assistant_id="outro"), ["bruno"])
        self.assertEqual(ids(action="auth.session_started"), ["ana"])
        self.assertEqual(
            ids(
                action="chat.question",
                occurred_from=datetime(2026, 10, 2, tzinfo=UTC),
                occurred_to=datetime(2026, 10, 2, 23, 59, tzinfo=UTC),
            ),
            ["bruno"],
        )

    def test_page_size_is_capped(self) -> None:
        for _ in range(3):
            DescribeCurrentUserUseCase(self.access.control).execute(self.rh_user)
        self.assertEqual(len(self._list(self.admin, limit=2)), 2)
        self.assertEqual(len(self._list(self.admin, limit=10_000)), 4)

    def test_invalid_period_is_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            AuditQuery(
                occurred_from=datetime(2026, 10, 3, tzinfo=UTC),
                occurred_to=datetime(2026, 10, 2, tzinfo=UTC),
            )

    def test_port_offers_no_update_or_delete(self) -> None:
        from src.domain import AuditLogRepository

        operations = {
            name for name in vars(AuditLogRepository) if not name.startswith("_")
        }
        self.assertEqual(operations, {"append", "list_events"})

    def test_event_is_immutable(self) -> None:
        event = AuditEvent(
            id="e1", user_id="u1", action="chat.question", resource_type="assistant"
        )
        with self.assertRaises(AttributeError):
            event.action = "outra"  # type: ignore[misc]
        self.assertGreater(
            event.occurred_at, datetime.now(UTC) - timedelta(minutes=1)
        )


class RetentionRepository:
    """Apaga do duble de trilha os eventos anteriores ao corte."""

    def __init__(self, audit_log) -> None:
        self.audit_log = audit_log
        self.cutoffs: list[datetime] = []

    def purge_older_than(self, cutoff: datetime) -> int:
        self.cutoffs.append(cutoff)
        before = len(self.audit_log.events)
        self.audit_log.events = [
            event for event in self.audit_log.events if event.occurred_at >= cutoff
        ]
        return before - len(self.audit_log.events)


class AuditRetentionTestCase(AccessTestCase):
    """D6 (RNF-24): limpeza por retencao, so pelo comando de manutencao."""

    NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)

    def _event(self, event_id: str, days_ago: int) -> AuditEvent:
        return AuditEvent(
            id=event_id,
            user_id="ana",
            action="chat.question",
            resource_type="assistant",
            occurred_at=self.NOW - timedelta(days=days_ago),
        )

    def _purge(self, retention_days: int):
        trail = AuditTrail(self.access.audit, clock=lambda: self.NOW)
        repository = RetentionRepository(self.access.audit)
        result = PurgeAuditEventsUseCase(
            retention_repository=repository,
            audit_trail=trail,
            clock=lambda: self.NOW,
        ).execute(PurgeAuditEventsInput(retention_days=retention_days))
        return result, repository

    def test_events_older_than_the_retention_are_removed(self) -> None:
        for event_id, days_ago in (("antigo", 400), ("limite", 365), ("novo", 10)):
            self.access.audit.append(self._event(event_id, days_ago))
        result, repository = self._purge(365)
        self.assertEqual(result.removed, 1)
        self.assertEqual(repository.cutoffs, [self.NOW - timedelta(days=365)])
        self.assertEqual(
            [event.id for event in self.access.audit.events[:2]], ["limite", "novo"]
        )

    def test_the_purge_itself_is_recorded_after_the_removal(self) -> None:
        self.access.audit.append(self._event("antigo", 400))
        self._purge(30)
        event = self.access.audit.events[-1]
        self.assertEqual(event.action, AuditAction.AUDIT_PURGED)
        self.assertEqual(event.user_id, MAINTENANCE_USER.id)
        self.assertEqual(event.details["removed"], 1)
        self.assertEqual(event.details["retention_days"], 30)

    def test_retention_below_one_day_is_rejected_before_removing(self) -> None:
        self.access.audit.append(self._event("antigo", 400))
        for days in (0, -5):
            with self.subTest(days=days), self.assertRaises(DomainValidationError):
                self._purge(days)
        self.assertEqual(len(self.access.audit.events), 1)

    def test_maintenance_identity_has_no_role(self) -> None:
        self.assertEqual(MAINTENANCE_USER.roles, frozenset())


if __name__ == "__main__":
    unittest.main()
