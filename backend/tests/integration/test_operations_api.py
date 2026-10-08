"""SPEC-006 pela API, com repositorios em memoria (CT-45).

Limite de uso (429 com ``Retry-After``), avaliacao das respostas, curadoria,
consumo e limites ajustados pelo administrador. Nao exige banco nem Qdrant.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from access_support import ADMIN, AccessHarness, member
from src.api.dependencies import (
    get_conversation_repository,
    get_feedback_repository,
    get_usage_record_repository,
    get_usage_settings,
    get_usage_settings_repository,
)
from src.api.errors import usage_limit_response
from src.api.routes import admin_router, feedback_router
from src.application.services import UsageGovernance, UsageSettings
from src.domain import (
    DAY,
    AssistantId,
    ChatMessage,
    Conversation,
    ConversationId,
    MessageId,
    MessageRole,
    Role,
    TokenUsage,
    UsageLimitExceededError,
    UsageLimits,
    UsageSummary,
    evaluate_usage_limits,
)

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
ASSISTANT = "assistant-1"
OWNER = member("user-1", "rh")
CURATOR = member("curadora", "rh", role=Role.CURATOR)


class Records:
    def __init__(self) -> None:
        self.records = []

    def append(self, record):
        self.records.append(record)
        return record

    def check(self, user_id, limits, now):
        moments = [
            r.occurred_at
            for r in self.records
            if r.user_id == user_id and r.occurred_at > now - DAY
        ]
        return evaluate_usage_limits(limits, moments, now)

    def summarize_by_user(self, query):
        by_user: dict[str, list] = {}
        for record in self.records:
            by_user.setdefault(record.user_id, []).append(record)
        return [
            UsageSummary(
                key=user_id,
                questions=len(items),
                input_tokens=sum(i.usage.input_tokens for i in items),
                output_tokens=sum(i.usage.output_tokens for i in items),
                estimated_cost=sum(i.estimated_cost for i in items),
                user_id=user_id,
                user_name=items[0].user_name,
            )
            for user_id, items in by_user.items()
        ]

    def summarize_by_conversation(self, query):
        return []


class Settings:
    def __init__(self) -> None:
        self.limits = None

    def get_limits(self):
        return self.limits

    def save_limits(self, limits, *, updated_by):
        self.limits = limits
        return limits


class Conversations:
    def __init__(self) -> None:
        conversation_id = ConversationId("conv-1")
        self.conversation = Conversation(
            id=conversation_id,
            assistant_id=AssistantId(ASSISTANT),
            owner_user_id=OWNER.id,
        )
        self.messages = [
            ChatMessage(
                id=MessageId("m-1"),
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content="Quanto duram as ferias?",
                created_at=NOW,
            ),
            ChatMessage(
                id=MessageId("m-2"),
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content="Vinte dias.",
                created_at=NOW + timedelta(seconds=1),
            ),
        ]

    def get_message(self, message_id):
        return next((m for m in self.messages if m.id.value == message_id), None)

    def get_by_id(self, conversation_id):
        return self.conversation if conversation_id == self.conversation.id else None

    def list_messages(self, conversation_id):
        return list(self.messages)


class Feedback:
    def __init__(self) -> None:
        self.items = {}

    def save(self, feedback):
        self.items[feedback.id] = feedback
        return feedback

    def get_by_id(self, feedback_id):
        return self.items.get(feedback_id)

    def get_by_message(self, message_id, user_id):
        return next(
            (
                f
                for f in self.items.values()
                if f.message_id == message_id and f.user_id == user_id
            ),
            None,
        )

    def list_feedback(self, query):
        if query.assistant_ids is not None and not query.assistant_ids:
            return []
        return [
            f
            for f in self.items.values()
            if (query.status is None or f.status is query.status)
            and (query.rating is None or f.rating is query.rating)
        ]


class UsageLimitResponseTestCase(unittest.TestCase):
    """Cenario "Limite de uso": 429 e quando perguntar de novo."""

    def test_429_carries_retry_after_and_the_next_window(self) -> None:
        response = usage_limit_response(
            UsageLimitExceededError(
                "usage limit reached.",
                window="minute",
                limit=20,
                retry_at=NOW + timedelta(seconds=42),
            ),
            now=NOW,
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["retry-after"], "43")
        self.assertIn(b'"retry_at":"2026-10-08T12:00:42+00:00"', response.body)
        self.assertIn(b'"code":"usage_limit"', response.body)


class OperationsApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(admin_router)
        self.app.include_router(feedback_router)
        self.harness = AccessHarness(self.app, OWNER)
        self.harness.link_assistant(ASSISTANT, "rh")
        self.records = Records()
        self.settings = Settings()
        self.feedback = Feedback()
        self.conversations = Conversations()
        overrides = self.app.dependency_overrides
        overrides[get_usage_record_repository] = lambda: self.records
        overrides[get_usage_settings_repository] = lambda: self.settings
        overrides[get_usage_settings] = UsageSettings
        overrides[get_feedback_repository] = lambda: self.feedback
        overrides[get_conversation_repository] = lambda: self.conversations
        self.client = TestClient(self.app)

    def as_user(self, user) -> None:
        self.harness.user = user

    def test_feedback_flow_from_user_to_curator(self) -> None:
        created = self.client.post(
            "/messages/m-2/feedback",
            json={"rating": "nao_util", "comment": "Sao trinta dias."},
        )
        self.assertEqual(created.status_code, 201)
        self.assertIsNone(created.json()["question"])

        self.as_user(OWNER)
        self.assertEqual(self.client.get("/feedback").status_code, 403)

        self.as_user(CURATOR)
        (item,) = self.client.get("/feedback").json()
        self.assertEqual(item["question"], "Quanto duram as ferias?")
        reviewed = self.client.post(
            f"/feedback/{item['id']}/review",
            json={
                "decision": "validado",
                "expected_answer": "Trinta dias.",
                "source_documents": ["politica.pdf"],
            },
        )
        self.assertEqual(reviewed.status_code, 200)
        again = self.client.post(
            f"/feedback/{item['id']}/review", json={"decision": "descartado"}
        )
        self.assertEqual(again.status_code, 409)
        exported = self.client.get("/feedback/export", params={"assistant_id": ASSISTANT})
        self.assertEqual(exported.status_code, 200)
        self.assertIn("Trinta dias.", exported.text)

    def test_feedback_on_someone_elses_message_is_not_found(self) -> None:
        self.as_user(member("user-2", "rh"))
        response = self.client.post("/messages/m-2/feedback", json={"rating": "util"})
        self.assertEqual(response.status_code, 404)

    def test_invalid_rating_is_rejected(self) -> None:
        response = self.client.post("/messages/m-2/feedback", json={"rating": "otimo"})
        self.assertEqual(response.status_code, 422)

    def test_admin_reads_consumption_and_adjusts_limits(self) -> None:
        UsageGovernance(
            limiter=self.records,
            record_repository=self.records,
            settings_repository=self.settings,
            settings=UsageSettings(),
        ).record(
            OWNER,
            conversation_id="conv-1",
            assistant_id=ASSISTANT,
            usage=TokenUsage(1000, 1000),
        )
        self.assertEqual(self.client.get("/admin/usage").status_code, 403)

        self.as_user(ADMIN)
        report = self.client.get("/admin/usage").json()
        self.assertTrue(report["estimated"])
        self.assertEqual(report["by_user"][0]["user_name"], "user-1")
        self.assertEqual(report["total_input_tokens"], 1000)

        self.assertEqual(self.client.get("/admin/usage-limits").json()["source"], "padrao")
        saved = self.client.put(
            "/admin/usage-limits", json={"per_minute": 5, "per_day": 100}
        )
        self.assertEqual(saved.json(), {"per_minute": 5, "per_day": 100, "source": "configurado"})
        self.assertEqual(self.settings.limits, UsageLimits(5, 100))
        invalid = self.client.put(
            "/admin/usage-limits", json={"per_minute": -1, "per_day": 100}
        )
        self.assertEqual(invalid.status_code, 422)


if __name__ == "__main__":
    unittest.main()
