"""fix-7 (rollback no commit), fix-8 (contagem sem mensagens) e fix-5 (tudo ou nada)."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from src.domain import AssistantId, Conversation, ConversationId


def _load_transactions():
    # O pacote do banco importa SQLAlchemy; o modulo em si nao precisa dele.
    path = (
        Path(__file__).resolve().parents[2]
        / "src/infrastructure/database/transactions.py"
    )
    spec = importlib.util.spec_from_file_location("transactions_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


commit_or_rollback = _load_transactions().commit_or_rollback


class FakeSession:
    def __init__(self, fail: Exception | None = None) -> None:
        self.fail = fail
        self.calls: list[str] = []

    def commit(self) -> None:
        self.calls.append("commit")
        if self.fail is not None:
            raise self.fail

    def rollback(self) -> None:
        self.calls.append("rollback")


class CommitOrRollbackTest(unittest.TestCase):
    def test_success_does_not_roll_back(self) -> None:
        session = FakeSession()
        commit_or_rollback(session)
        self.assertEqual(session.calls, ["commit"])

    def test_failure_rolls_back_and_reraises_the_original_error(self) -> None:
        error = RuntimeError("integrity")
        session = FakeSession(fail=error)
        with self.assertRaises(RuntimeError) as caught:
            commit_or_rollback(session)
        self.assertIs(caught.exception, error)
        self.assertEqual(session.calls, ["commit", "rollback"])


class ConversationCountTest(unittest.TestCase):
    def test_summary_uses_the_total_without_messages(self) -> None:
        conversation = Conversation(
            id=ConversationId("c1"),
            assistant_id=AssistantId("a1"),
            message_total=7,
        )
        self.assertEqual(conversation.messages, ())
        self.assertEqual(conversation.message_count, 7)

    def test_full_conversation_counts_its_messages(self) -> None:
        conversation = Conversation(
            id=ConversationId("c1"), assistant_id=AssistantId("a1")
        )
        self.assertEqual(conversation.message_count, 0)


class MigrationShapeTest(unittest.TestCase):
    def test_0008_chains_after_0007_and_is_importable(self) -> None:
        versions = (
            Path(__file__).resolve().parents[2]
            / "src/infrastructure/database/alembic/versions"
        )
        try:
            import alembic  # noqa: F401
        except ImportError:
            self.skipTest("alembic indisponivel")
        spec = importlib.util.spec_from_file_location(
            "m0008", versions / "0008_indexes_and_constraints.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.down_revision, "0007_reindex_in_worker")


if __name__ == "__main__":
    unittest.main()
