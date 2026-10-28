"""SPEC-20261007-004: acesso pela API (CT-26, CT-27, CT-29, CT-30).

Usa repositorios em memoria e um verificador de token local; nao precisa do
Keycloak nem do banco. Execute dentro do container do backend.
"""

from __future__ import annotations

from dataclasses import replace

import re
import unittest

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from access_support import AccessHarness, TokenFactory, bearer, member
from src.api.dependencies import (
    get_llm_credential_repository,
    get_llm_gateway_builder,
    get_answer_generator,
    get_usage_governance,
    get_assistant_repository,
    get_audit_log_repository,
    get_context_retriever,
    get_conversation_repository,
    get_document_repository,
    get_embedding_gateway,
    get_llm_insecure_http_allowed,
    get_llm_test_gateway_factory,
    get_reindex_job_repository,
    get_retrieval_defaults,
    get_secret_cipher,
    get_token_counter,
    get_token_verifier,
    get_vector_store_gateway,
)
from src.api.routes import (
    admin_router,
    assistant_settings_router,
    assistants_router,
    llm_credential_options_router,
    llm_credentials_router,
    conversations_router,
    document_access_router,
    documents_router,
    index_router,
    me_router,
)
from src.application.services import (
    ContextRetriever,
    GroundedAnswerGenerator,
    RetrievalSettings,
)
from src.domain import (
    Assistant,
    AssistantId,
    AssistantName,
    ChatMessage,
    CollectionName,
    Conversation,
    ConversationId,
    DocumentId,
    LLMCredential,
    LLMCredentialId,
    RetrievalDefaults,
    Role,
    SearchResult,
    SparseVector,
)
from src.infrastructure.embeddings import Bm25SparseEmbeddingGateway
from src.infrastructure.llm import FakeContextAwareLLM

RH = "assistant-rh"
ORPHAN = "assistant-sem-grupo"
ANA = member("ana", "rh")
BRUNO = member("bruno", "financeiro")
OPENAI_CREDENTIAL = {
    "name": "OpenAI",
    "provider": "openai",
    "models": [{"name": "gpt-4o-mini"}, {"name": "gpt-4o"}],
    "default_model": "gpt-4o-mini",
    # Chave ficticia.
    "api_key": "sk-live-ficticia",
}

ALL_ROUTERS = (
    admin_router,
    assistant_settings_router,
    assistants_router,
    llm_credential_options_router,
    llm_credentials_router,
    conversations_router,
    document_access_router,
    documents_router,
    index_router,
    me_router,
)


class InMemoryLLMCredentials:
    """SPEC-013: credenciais em memoria; a chave fica so cifrada, a parte."""

    def __init__(self) -> None:
        self.items: dict[str, LLMCredential] = {}
        self.keys: dict[str, str] = {}

    def list_all(self) -> list[LLMCredential]:
        return sorted(self.items.values(), key=lambda item: (not item.is_default, item.name))

    def get(self, credential_id: LLMCredentialId) -> LLMCredential | None:
        return self.items.get(credential_id.value)

    def get_default(self) -> LLMCredential | None:
        return next((item for item in self.items.values() if item.is_default), None)

    def get_encrypted_key(self, credential_id: LLMCredentialId) -> str | None:
        return self.keys.get(credential_id.value)

    def save(self, credential, *, encrypted_key, updated_by):
        if credential.is_default:
            for key, item in list(self.items.items()):
                if key != credential.id.value and item.is_default:
                    self.items[key] = item.with_default(False)
        if encrypted_key is not None:
            self.keys[credential.id.value] = encrypted_key
        stored = credential.with_key_configured(credential.id.value in self.keys)
        self.items[credential.id.value] = stored
        return stored

    def set_default(self, credential_id, *, updated_by):
        for key, item in list(self.items.items()):
            self.items[key] = item.with_default(key == credential_id.value)

    def delete(self, credential_id) -> bool:
        self.keys.pop(credential_id.value, None)
        return self.items.pop(credential_id.value, None) is not None


class AssistantRepository:
    def __init__(self) -> None:
        self.items = {
            item: Assistant(id=AssistantId(item), name=AssistantName(item))
            for item in (RH, ORPHAN)
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

    def update_llm_choice(self, assistant_id, *, credential_id, model):
        current = self.items.get(assistant_id.value)
        if current is None:
            return None
        self.items[assistant_id.value] = replace(
            current, llm_credential_id=credential_id, llm_model=model
        )
        return self.items[assistant_id.value]

    def update_retrieval_profile(self, assistant_id, profile):
        current = self.items.get(assistant_id.value)
        if current is None:
            return None
        self.items[assistant_id.value] = replace(current, retrieval_profile=profile)
        return self.items[assistant_id.value]


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
        self, assistant_id: AssistantId, owner_user_id: str
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
                assistant_id=AssistantId(RH),
                owner_user_id=owner,
            )
        )


class RecordingVectorStore:
    def __init__(self) -> None:
        self.searches: list[frozenset[str] | None] = []

    def hybrid_search(
        self,
        collection_name: CollectionName,
        dense_vector: list[float],
        sparse_vector: SparseVector,
        limit: int,
        payload_filter: dict[str, str] | None = None,
        *,
        user_groups: frozenset[str] | None,
    ) -> list[SearchResult]:
        self.searches.append(user_groups)
        return [
            SearchResult(
                chunk_id="doc-1:0",
                document_id=DocumentId("doc-1"),
                score=0.9,
                text="As ferias sao de trinta dias.",
                source_name="politica.md",
            )
        ]

    def resolve_alias(self, alias: CollectionName) -> CollectionName | None:
        return None

    def delete_collection(self, collection_name: CollectionName) -> None:
        return None


class EmptyDocumentRepository:
    def list_by_assistant(self, assistant_id: AssistantId) -> list:
        return []

    def get_by_id(self, document_id: DocumentId) -> None:
        return None


class IdleJobRepository:
    def get_running(self, assistant_id: AssistantId) -> None:
        return None

    def get_latest(self, assistant_id: AssistantId) -> None:
        return None


class OneVectorEmbedding:
    model_name = "fake"
    dimension = 1

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0]


class KeepScoreReranker:
    model_name = "fake-reranker"

    def rerank(self, query: str, candidates: list[SearchResult]) -> list[SearchResult]:
        return list(candidates)


class WordTokenCounter:
    max_tokens = 128

    def count(self, text: str) -> int:
        return len(text.split())


class Cipher:
    def encrypt(self, plaintext: str) -> str:
        return f"enc::{plaintext}"

    def decrypt(self, ciphertext: str) -> str:
        return ciphertext.removeprefix("enc::")


class ApiAccessTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        for router in ALL_ROUTERS:
            self.app.include_router(router)
        self.access = AccessHarness(self.app, ANA)
        self.access.link_assistant(RH, "rh")
        self.assistants = AssistantRepository()
        self.conversations = ConversationRepository()
        self.vector_store = RecordingVectorStore()
        self.credentials = InMemoryLLMCredentials()
        retriever = ContextRetriever(
            embedding_gateway=OneVectorEmbedding(),
            sparse_embedding_gateway=Bm25SparseEmbeddingGateway(),
            vector_store_gateway=self.vector_store,
            reranker_gateway=KeepScoreReranker(),
            settings=RetrievalSettings(),
        )
        overrides = self.app.dependency_overrides
        overrides[get_assistant_repository] = lambda: self.assistants
        overrides[get_conversation_repository] = lambda: self.conversations
        overrides[get_vector_store_gateway] = lambda: self.vector_store
        overrides[get_context_retriever] = lambda: retriever
        overrides[get_answer_generator] = lambda: GroundedAnswerGenerator(
            llm_gateway=FakeContextAwareLLM()
        )
        # SPEC-013: o LLM e resolvido por assistente; troca-se o construtor.
        overrides[get_llm_credential_repository] = lambda: self.credentials
        overrides[get_llm_gateway_builder] = lambda: lambda _resolved: FakeContextAwareLLM()
        overrides[get_token_counter] = WordTokenCounter
        overrides[get_secret_cipher] = Cipher
        overrides[get_llm_insecure_http_allowed] = lambda: False
        overrides[get_llm_test_gateway_factory] = lambda: lambda _c, _k: FakeContextAwareLLM()
        overrides[get_retrieval_defaults] = lambda: RetrievalDefaults(
            candidates=30, top_k=5, min_score=0.10
        )
        overrides[get_audit_log_repository] = lambda: self.access.audit
        overrides[get_usage_governance] = lambda: None
        # Nenhum teste daqui toca o banco nem carrega o modelo de embedding.
        overrides[get_document_repository] = EmptyDocumentRepository
        overrides[get_reindex_job_repository] = IdleJobRepository
        overrides[get_embedding_gateway] = OneVectorEmbedding
        self.client = TestClient(self.app)

    def acting_as(self, user) -> TestClient:
        self.access.user = user
        return self.client


class UnauthenticatedTestCase(unittest.TestCase):
    """CT-26 (RF-40): sem token, toda rota exceto /health responde 401."""

    def setUp(self) -> None:
        from src.api.main import app

        self.app = app
        self.tokens = TokenFactory()
        app.dependency_overrides[get_token_verifier] = self.tokens.verifier
        self.addCleanup(app.dependency_overrides.clear)
        # Sem ``with``: a subida da aplicacao (migracoes) nao e executada.
        self.client = TestClient(app)

    def _protected_routes(self) -> list[tuple[str, str]]:
        routes = []
        for route in self.app.routes:
            # /health e /metrics sao publicos por projeto (SPEC-006 D2).
            if not isinstance(route, APIRoute) or route.path in ("/health", "/metrics"):
                continue
            path = re.sub(r"\{[^}]+\}", "x", route.path)
            routes.extend((method, path) for method in sorted(route.methods))
        return routes

    def test_every_route_but_health_requires_a_token(self) -> None:
        routes = self._protected_routes()
        self.assertGreaterEqual(len(routes), 18)
        for method, path in routes:
            with self.subTest(route=f"{method} {path}"):
                response = self.client.request(method, path)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(
                    response.json(),
                    {"detail": "authentication required", "code": "unauthenticated"},
                )
                self.assertEqual(response.headers["www-authenticate"], "Bearer")

    def test_health_needs_no_token(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_invalid_tokens_are_rejected_on_every_route(self) -> None:
        other_issuer = TokenFactory()
        bad_tokens = {
            "malformed": "abc.def",
            "other key": other_issuer.token("ana", roles=("nexus-admin",)),
            "issuer": self.tokens.token("ana", iss="http://evil.test/realms/nexus"),
            "audience": self.tokens.token("ana", aud=["nexus-frontend"]),
            "expired": self.tokens.token("ana", exp=1),
        }
        for method, path in self._protected_routes():
            for label, token in bad_tokens.items():
                with self.subTest(route=f"{method} {path}", token=label):
                    response = self.client.request(method, path, headers=bearer(token))
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(
                        response.json(),
                        {"detail": "invalid or expired token", "code": "unauthenticated"},
                    )

    def test_other_authorization_schemes_are_rejected(self) -> None:
        token = self.tokens.token("ana", roles=("nexus-usuario",))
        for header in (f"Basic {token}", token, "Bearer", "Bearer   "):
            with self.subTest(header=header[:12]):
                response = self.client.get("/me", headers={"Authorization": header})
                self.assertEqual(response.status_code, 401)


class AssistantGroupsTestCase(ApiAccessTestCase):
    """CT-27 (RF-42) e o cenario "Assistente sem grupo"."""

    def test_listing_shows_only_the_assistants_of_the_user_groups(self) -> None:
        listed = self.acting_as(ANA).get("/assistants").json()
        self.assertEqual([item["id"] for item in listed], [RH])
        self.assertEqual(self.acting_as(BRUNO).get("/assistants").json(), [])

    def test_assistant_without_group_appears_only_to_the_administrator(self) -> None:
        admin = member("root", role=Role.ADMIN)
        listed = self.acting_as(admin).get("/assistants").json()
        self.assertEqual({item["id"] for item in listed}, {RH, ORPHAN})
        self.assertEqual(
            {item["id"]: item["groups"] for item in listed},
            {RH: ["rh"], ORPHAN: []},
        )

    def test_user_of_another_group_cannot_open_a_conversation(self) -> None:
        response = self.acting_as(BRUNO).post(
            "/conversations", json={"assistant_id": RH}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.conversations.items, {})
        denial = self.access.audit.events[-1]
        self.assertEqual(denial.action, "access.denied")
        self.assertEqual(denial.user_id, "bruno")
        self.assertEqual(denial.details["assistant_id"], RH)

    def test_user_of_another_group_gets_403_on_the_chat_api(self) -> None:
        # Conversa aberta quando o usuario ainda tinha acesso ao assistente.
        self.conversations.add("conv-bruno", "bruno")
        response = self.acting_as(BRUNO).post(
            "/conversations/conv-bruno/chat",
            json={"question": "Quanto duram as ferias?"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("ferias", response.text)
        self.assertEqual(self.vector_store.searches, [])
        self.assertEqual(self.conversations.messages, [])
        denial = self.access.audit.events[-1]
        self.assertEqual(denial.action, "access.denied")
        self.assertEqual(denial.details["attempted_action"], "chat.question")

    def test_other_assistant_routes_are_denied_too(self) -> None:
        client = self.acting_as(BRUNO)
        self.assertEqual(client.get(f"/assistants/{RH}/conversations").status_code, 403)
        self.assertEqual(client.get(f"/assistants/{RH}/documents").status_code, 403)
        self.assertEqual(client.get(f"/assistants/{RH}/index-status").status_code, 403)
        self.assertEqual(client.post(f"/assistants/{RH}/reindex").status_code, 403)

    def test_member_chats_and_the_search_carries_its_groups(self) -> None:
        self.conversations.add("conv-ana", "ana")
        response = self.acting_as(ANA).post(
            "/conversations/conv-ana/chat",
            json={"question": "Quanto duram as ferias?"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["fallback_used"])
        self.assertEqual(self.vector_store.searches, [frozenset({"rh"})])
        self.assertEqual(self.access.audit.events[-1].action, "chat.question")

    def test_only_the_administrator_links_groups(self) -> None:
        denied = self.acting_as(member("carla", "rh", role=Role.CURATOR)).put(
            f"/assistants/{ORPHAN}/groups", json={"groups": ["rh"]}
        )
        self.assertEqual(denied.status_code, 403)
        allowed = self.acting_as(member("root", role=Role.ADMIN)).put(
            f"/assistants/{ORPHAN}/groups", json={"groups": ["/rh", "financeiro"]}
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json(), {"groups": ["financeiro", "rh"]})
        listed = self.acting_as(BRUNO).get("/assistants").json()
        self.assertEqual([item["id"] for item in listed], [ORPHAN])

    def test_only_the_administrator_creates_and_deletes_assistants(self) -> None:
        curator = member("carla", "rh", role=Role.CURATOR)
        created = self.acting_as(curator).post("/assistants", json={"name": "Novo"})
        deleted = self.acting_as(curator).delete(f"/assistants/{RH}")
        self.assertEqual((created.status_code, deleted.status_code), (403, 403))
        self.assertIn(RH, self.assistants.items)


class ConversationPrivacyTestCase(ApiAccessTestCase):
    """CT-29 (RF-44, RN-24)."""

    def setUp(self) -> None:
        super().setUp()
        self.conversations.add("conv-ana", "ana")
        self.conversations.add("conv-antiga", None)

    def _attempts(self, client: TestClient, conversation_id: str) -> dict[str, int]:
        base = f"/conversations/{conversation_id}"
        return {
            "get": client.get(base).status_code,
            "message": client.post(
                f"{base}/messages", json={"role": "user", "content": "Oi"}
            ).status_code,
            "chat": client.post(f"{base}/chat", json={"question": "Oi?"}).status_code,
            "delete": client.delete(base).status_code,
        }

    def test_conversation_of_another_user_answers_404(self) -> None:
        same_group = member("davi", "rh")
        attempts = self._attempts(self.acting_as(same_group), "conv-ana")
        self.assertEqual(set(attempts.values()), {404})
        self.assertIn("conv-ana", self.conversations.items)
        self.assertEqual(self.conversations.messages, [])

    def test_owner_cannot_forge_assistant_or_system_messages(self) -> None:
        """SPEC-007 fix-1: so o papel ``user`` entra por esta rota."""
        client = self.acting_as(member("ana", "rh"))
        for role in ("assistant", "system"):
            response = client.post(
                "/conversations/conv-ana/messages",
                json={"role": role, "content": "Politica falsa"},
            )
            self.assertEqual(response.status_code, 422, role)
        self.assertEqual(self.conversations.messages, [])

    def test_administrator_does_not_read_conversations_of_others(self) -> None:
        admin = member("root", role=Role.ADMIN)
        attempts = self._attempts(self.acting_as(admin), "conv-ana")
        self.assertEqual(set(attempts.values()), {404})

    def test_conversation_from_before_authentication_is_hidden(self) -> None:
        for user in (ANA, member("root", role=Role.ADMIN)):
            with self.subTest(user=user.id):
                attempts = self._attempts(self.acting_as(user), "conv-antiga")
                self.assertEqual(set(attempts.values()), {404})
        self.assertIn("conv-antiga", self.conversations.items)

    def test_unknown_and_foreign_conversations_are_indistinguishable(self) -> None:
        client = self.acting_as(member("davi", "rh"))
        foreign = client.get("/conversations/conv-ana")
        unknown = client.get("/conversations/nao-existe")
        self.assertEqual(foreign.json(), unknown.json())

    def test_owner_reads_lists_and_deletes_its_conversation(self) -> None:
        client = self.acting_as(ANA)
        created = client.post("/conversations", json={"assistant_id": RH})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(client.get("/conversations/conv-ana").status_code, 200)
        listed = client.get(f"/assistants/{RH}/conversations").json()
        self.assertEqual(
            {item["id"] for item in listed}, {"conv-ana", created.json()["id"]}
        )
        self.assertEqual(client.delete("/conversations/conv-ana").status_code, 204)


class RolesFromTokenTestCase(ApiAccessTestCase):
    """CT-30 (RF-41, RF-47): os papeis vem do token, validado de verdade."""

    def setUp(self) -> None:
        super().setUp()
        self.tokens = TokenFactory()
        verifier = self.tokens.verifier()
        self.access.use_tokens({})
        self.app.dependency_overrides[get_token_verifier] = lambda: verifier

    def _admin_routes(self, token: str) -> dict[str, int]:
        headers = bearer(token)
        return {
            "list": self.client.get("/admin/llm-credentials", headers=headers).status_code,
            "save": self.client.post(
                "/admin/llm-credentials", json=OPENAI_CREDENTIAL, headers=headers
            ).status_code,
            "test": self.client.post(
                "/admin/llm-credentials/x/test", json={}, headers=headers
            ).status_code,
            "options": self.client.get("/llm-credentials/options", headers=headers).status_code,
            "audit": self.client.get("/admin/audit-events", headers=headers).status_code,
        }

    def test_llm_key_routes_answer_403_to_non_administrators(self) -> None:
        for role in ("nexus-curador", "nexus-usuario"):
            with self.subTest(role=role):
                token = self.tokens.token("carla", roles=(role,), groups=("rh",))
                self.assertEqual(set(self._admin_routes(token).values()), {403})
        self.assertEqual(self.credentials.items, {})

    def test_token_without_a_nexus_role_is_denied(self) -> None:
        token = self.tokens.token("visitante", roles=("offline_access",), groups=("rh",))
        self.assertEqual(set(self._admin_routes(token).values()), {403})
        listed = self.client.get("/assistants", headers=bearer(token))
        self.assertEqual(listed.json(), [])

    def test_administrator_role_in_the_token_opens_the_routes(self) -> None:
        token = self.tokens.token("root", roles=("nexus-admin",))
        headers = bearer(token)
        saved = self.client.post(
            "/admin/llm-credentials", json=OPENAI_CREDENTIAL, headers=headers
        )
        self.assertEqual(saved.status_code, 201)
        self.assertEqual(list(self.credentials.keys.values()), ["enc::sk-live-ficticia"])
        listed = self.client.get("/admin/llm-credentials", headers=headers)
        self.assertTrue(listed.json()["items"][0]["key_configured"])
        self.assertNotIn("sk-live-ficticia", listed.text + saved.text)
        self.assertNotIn("sk-live-ficticia", repr(self.access.audit.events))

    def test_me_returns_identity_roles_and_groups_from_the_token(self) -> None:
        token = self.tokens.token(
            "carla", roles=("nexus-curador", "uma_authorization"), groups=("/rh",)
        )
        response = self.client.get("/me", headers=bearer(token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"id": "carla", "name": "carla", "roles": ["nexus-curador"], "groups": ["rh"]},
        )


class AuditApiTestCase(ApiAccessTestCase):
    """Cenario "Auditoria" e a parte de API do CT-31."""

    def test_administrator_sees_who_asked_and_which_documents_were_used(self) -> None:
        self.conversations.add("conv-ana", "ana")
        self.acting_as(ANA).post(
            "/conversations/conv-ana/chat",
            json={"question": "Quanto duram as ferias?"},
        )
        admin = member("root", role=Role.ADMIN)
        response = self.acting_as(admin).get(
            "/admin/audit-events", params={"action": "chat.question"}
        )
        self.assertEqual(response.status_code, 200)
        (event,) = response.json()
        self.assertEqual(event["user_id"], "ana")
        self.assertEqual(event["resource_id"], RH)
        self.assertIn("occurred_at", event)
        self.assertEqual(
            [item["source_name"] for item in event["details"]["retrieved_documents"]],
            ["politica.md"],
        )
        self.assertNotIn("trinta dias", response.text)
        self.assertNotIn("Quanto duram", response.text)

    def test_trail_offers_no_change_or_removal(self) -> None:
        client = self.acting_as(member("root", role=Role.ADMIN))
        client.get("/me")
        for method in ("put", "patch", "delete", "post"):
            with self.subTest(method=method):
                response = client.request(method, "/admin/audit-events")
                self.assertEqual(response.status_code, 405)
                item = client.request(method, "/admin/audit-events/qualquer-id")
                self.assertIn(item.status_code, (404, 405))
        self.assertIn("auth.session_started", self.access.audit.actions())


class LLMCredentialsApiTestCase(ApiAccessTestCase):
    """SPEC-013 CT-109: rotas de credenciais e da configuracao do assistente."""

    def setUp(self) -> None:
        super().setUp()
        self.admin = member("root", role=Role.ADMIN)
        self.curator = member("carla", "rh", role=Role.CURATOR)

    def create(self, **changes: object) -> dict:
        response = self.acting_as(self.admin).post(
            "/admin/llm-credentials", json={**OPENAI_CREDENTIAL, **changes}
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_list_offers_presets_and_currency(self) -> None:
        self.create()
        body = self.acting_as(self.admin).get("/admin/llm-credentials").json()
        self.assertIn("gemini", body["provider_urls"])
        self.assertTrue(body["currency"])
        (item,) = body["items"]
        self.assertTrue(item["is_default"])
        self.assertNotIn("api_key", item)

    def test_preset_fixes_the_url_and_prices_are_kept(self) -> None:
        created = self.create(
            name="Gemini",
            provider="gemini",
            api_url="https://outro.exemplo.com/v1/chat",
            models=[{"name": "gemini-flash", "input_per_1k": "0.0001", "output_per_1k": "0.0004"}],
            default_model="gemini-flash",
        )
        self.assertTrue(created["api_url"].startswith("https://generativelanguage"))
        self.assertEqual(created["models"][0]["output_per_1k"], "0.0004")

    def test_invalid_input_answers_422(self) -> None:
        client = self.acting_as(self.admin)
        for changes in (
            {"provider": "custom", "api_url": "http://inseguro.exemplo.com/v1"},
            {"provider": "custom", "api_url": "https://x.exemplo.com/v1?key=1"},
            {"default_model": "nao-listado"},
            {"provider": "azure"},
            {"models": []},
            {"api_key": ""},
        ):
            with self.subTest(changes=changes):
                response = client.post(
                    "/admin/llm-credentials", json={**OPENAI_CREDENTIAL, **changes}
                )
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.credentials.items, {})

    def test_validation_error_never_echoes_the_key(self) -> None:
        # RN-39: no Pydantic 2 o erro de campo ausente traz o corpo em ``input``.
        body = {key: value for key, value in OPENAI_CREDENTIAL.items() if key != "models"}
        response = self.acting_as(self.admin).post("/admin/llm-credentials", json=body)
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("sk-live-ficticia", response.text)

    def test_default_cannot_be_deleted_and_answers_409_with_followers(self) -> None:
        created = self.create()
        response = self.acting_as(self.admin).delete(f"/admin/llm-credentials/{created['id']}")
        self.assertEqual(response.status_code, 409)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "llm_credential_in_use")
        self.assertTrue(detail["is_default"])
        self.assertIn(RH, detail["assistant_ids"])

    def test_new_destination_without_key_answers_422(self) -> None:
        created = self.create()
        response = self.acting_as(self.admin).put(
            f"/admin/llm-credentials/{created['id']}",
            json={
                "name": "OpenAI",
                "provider": "custom",
                "api_url": "https://llm.exemplo.com/v1/chat/completions",
                "models": [{"name": "gpt-4o-mini"}],
                "default_model": "gpt-4o-mini",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_test_route_uses_the_credential(self) -> None:
        created = self.create()
        response = self.acting_as(self.admin).post(
            f"/admin/llm-credentials/{created['id']}/test", json={"model": "gpt-4o-mini"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["model"], "gpt-4o-mini")
        missing = self.acting_as(self.admin).post("/admin/llm-credentials/nada/test", json={})
        self.assertEqual(missing.status_code, 404)

    def test_assistant_llm_is_set_by_the_admin_and_read_by_the_curator(self) -> None:
        created = self.create()
        response = self.acting_as(self.admin).put(
            f"/assistants/{RH}/llm",
            json={"credential_id": created["id"], "model": "gpt-4o"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["source"], "assistant")
        read = self.acting_as(self.curator).get(f"/assistants/{RH}/llm")
        self.assertEqual(read.status_code, 200)
        self.assertEqual(read.json()["effective_model"], "gpt-4o")
        denied = self.acting_as(self.curator).put(f"/assistants/{RH}/llm", json={})
        self.assertEqual(denied.status_code, 403)
        unknown = self.acting_as(self.admin).put(
            f"/assistants/{RH}/llm", json={"credential_id": "nada"}
        )
        self.assertEqual(unknown.status_code, 422)

    def test_retrieval_settings_by_the_curator_with_limits(self) -> None:
        client = self.acting_as(self.curator)
        body = client.get(f"/assistants/{RH}/retrieval-settings").json()
        self.assertEqual(body["min_score"]["origin"], "default")
        self.assertEqual(body["limits"]["candidates"], [5, 100])
        saved = client.put(
            f"/assistants/{RH}/retrieval-settings",
            json={"min_score": 0.3, "hybrid_enabled": False},
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["min_score"]["effective"], 0.3)
        self.assertFalse(saved.json()["hybrid_enabled"]["effective"])
        for payload in ({"top_k": 21}, {"candidates": "30"}, {"hybrid_enabled": "sim"}):
            with self.subTest(payload=payload):
                self.assertEqual(
                    client.put(f"/assistants/{RH}/retrieval-settings", json=payload).status_code,
                    422,
                )
        other = client.put(f"/assistants/{ORPHAN}/retrieval-settings", json={"top_k": 3})
        self.assertEqual(other.status_code, 403)


if __name__ == "__main__":
    unittest.main()
